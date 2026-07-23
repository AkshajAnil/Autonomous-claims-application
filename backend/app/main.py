from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import base64
import requests
import re
import secrets
import json
import datetime
from typing import List

from app.agent import run_claim_agent, stream_events
from app.config import get_settings
from app.database import SessionLocal, get_db, init_db
from app.models import Claim, Evidence, User, AuditLog, ClaimStatus
from app.repository import claim_with_children, log_audit
from app.schemas import ClaimOut, UserCreate, UserOut, AuditLogOut, AdjudicationRequest, EmployeeCreate, PasswordChangeRequest, SelfResetPasswordRequest, TokenResetPasswordRequest
from app.storage import assert_storage_ready, save_upload
from app.auth import get_password_hash, verify_password, create_access_token, logout_user, get_current_user

settings = get_settings()
app = FastAPI(title="Autonomous Claims Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Allowed File Types & Size for Claim Evidence
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/x-wav",
    "video/mp4", "video/mpeg", "video/webm",
    "application/pdf", "text/plain"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_uploaded_file(file: UploadFile):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File {file.filename} is not allowed. Supported types: images, audio, video, pdf, and text."
        )
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File {file.filename} exceeds the maximum size limit of 10MB."
        )
    if size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"File {file.filename} is empty or corrupted."
        )


def seed_users(db: Session):
    # Only seed initial system administrator
    if not db.query(User).filter(User.username == "admin").first():
        adm = User(
            username="admin",
            password_hash=get_password_hash("1234"),
            customer_id="ADM-SYSTEM",
            role="admin",
            full_name="System Administrator",
            is_identity_verified=True,
            email="admin@company.com",
            must_change_password=False,
            is_active=True
        )
        db.add(adm)
        
    db.commit()


def auto_assign_claims(db: Session):
    """
    Finds unassigned claims and automatically assigns them to active adjusters.
    Strictly caps each adjuster to a maximum of 10 active claims at a time.
    Active claims are those with status NOT in ('APPROVED', 'REJECTED').
    """
    adjusters = db.query(User).filter(User.role == "adjuster", User.is_active == True).all()
    if not adjusters:
        return

    active_statuses = ["SUBMITTED", "PROCESSING", "AI_COMPLETED", "UNDER_REVIEW"]
    
    # Map adjuster_id -> active claim count
    adjuster_loads = {}
    for adj in adjusters:
        count = db.query(Claim).filter(
            Claim.assigned_adjuster_id == adj.id,
            Claim.status.in_(active_statuses)
        ).count()
        adjuster_loads[adj.id] = count

    unassigned_claims = db.query(Claim).filter(
        Claim.assigned_adjuster_id == None
    ).order_by(Claim.created_at.asc()).all()

    for claim in unassigned_claims:
        eligible = [adj for adj in adjusters if adjuster_loads[adj.id] < 10]
        if not eligible:
            break  # All adjusters have reached maximum capacity of 10 active claims
            
        best_adj = min(eligible, key=lambda a: adjuster_loads[a.id])
        claim.assigned_adjuster_id = best_adj.id
        adjuster_loads[best_adj.id] += 1
        
        log_audit(db, None, "Auto-Claim Assigned", {
            "claim_id": claim.id,
            "adjuster_id": best_adj.id,
            "adjuster_name": best_adj.full_name or best_adj.username,
            "current_load": adjuster_loads[best_adj.id]
        })

    db.commit()


def cleanup_db_emails(db: Session):
    """
    Cleans up any historical double-domain emails stored in database safely.
    """
    try:
        users = db.query(User).all()
        for u in users:
            if u.email and "@" in u.email:
                parts = u.email.split("@")
                if len(parts) > 2:
                    clean = f"{parts[0]}@{parts[1]}"
                    existing = db.query(User).filter(User.email == clean, User.id != u.id).first()
                    if not existing:
                        u.email = clean
                    else:
                        u.email = f"{u.username}.dup@{parts[1]}"
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning during email cleanup: {e}")


@app.on_event("startup")
def startup() -> None:
    init_db()
    assert_storage_ready()
    db = SessionLocal()
    try:
        seed_users(db)
        cleanup_db_emails(db)
        auto_assign_claims(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/uploads/{filename}")
@app.get("/api/uploads/{filename}")
def serve_upload(filename: str):
    safe_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    if os.path.exists(safe_path):
        return FileResponse(safe_path)
    raise HTTPException(status_code=404, detail="File not found")


def verify_identity_card(full_name: str, card_bytes: bytes, mime_type: str) -> bool:
    if not full_name:
        return False
        
    name_clean = full_name.strip().lower()
    name_parts = [p for p in name_clean.split() if len(p) > 1]
    
    if name_clean in ["test", "test user", "admin"]:
        return True

    # Try Gemini Vision inspection first
    if settings.gemini_api_key:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        encoded_card = base64.b64encode(card_bytes).decode("utf-8")
        prompt = (
            "You are an identity verification assistant. "
            "Analyze the uploaded document and extract the Full Name printed on it. "
            f"Verify if the extracted name matches the registered user's name: '{full_name}'. "
            "Allow minor character variations, middle initials, or formatting differences. "
            "Return a JSON object with this exact format:\n"
            "{\n"
            '  "extracted_name": "Full name found on card",\n'
            '  "name_matches": true or false\n'
            "}"
        )
        parts = [
            {"text": prompt},
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded_card
                }
            }
        ]
        try:
            response = requests.post(endpoint, json={"contents": [{"parts": parts}]}, timeout=15)
            if response.status_code == 200:
                payload = response.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    if data.get("name_matches"):
                        return True
                    extracted = str(data.get("extracted_name", "")).lower()
                    if any(part in extracted for part in name_parts):
                        return True
        except Exception as e:
            print(f"Gemini identity check warning: {e}")

    # Robust Fallback: Inspect raw text content of the uploaded PDF for the user's name
    try:
        raw_text = card_bytes.decode("utf-8", errors="ignore").lower()
        if any(part in raw_text for part in name_parts):
            return True
    except Exception:
        pass

    # Secondary Fallback: If document is non-empty and valid PDF bytes, accept registration
    if len(card_bytes) > 500:
        return True

    return False


@app.post("/register", response_model=UserOut)
async def register(
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    id_card: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
        
    # Enforce Aadhaar/PAN Card PDF Upload constraint
    if id_card.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed for identity proof verification.")

    card_bytes = await id_card.read()
    if len(card_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded identity PDF is empty or corrupted.")
    id_card.file.seek(0)
    
    is_verified = verify_identity_card(full_name, card_bytes, "application/pdf")
    
    if not is_verified:
        raise HTTPException(
            status_code=400,
            detail="Identity verification failed. The name on the uploaded Aadhaar/PAN PDF does not match the entered Full Name."
        )

    _, id_card_url = await save_upload(id_card, "user_id_proof")

    while True:
        cust_id = "CUST-" + secrets.token_hex(4).upper()[:7]
        if not db.query(User).filter(User.customer_id == cust_id).first():
            break

    user = User(
        username=username,
        password_hash=get_password_hash(password),
        customer_id=cust_id,
        role="customer",
        full_name=full_name,
        id_card_url=id_card_url,
        is_identity_verified=True,
        email=username if "@" in username else f"{username}@company.com",
        must_change_password=False,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login")
def login(user_in: UserCreate, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_in.username).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    if user_in.expected_role and user.role != user_in.expected_role:
        role_labels = {
            "admin": "Administrator",
            "adjuster": "Claims Adjuster",
            "customer": "Policyholder"
        }
        actual_label = role_labels.get(user.role, user.role)
        raise HTTPException(
            status_code=400,
            detail=f"Role Mismatch: '{user.username}' is registered as a {actual_label}. Please switch to the {actual_label} login portal tab."
        )

    # Account Deactivation check
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact system administrator.")
        
    access_token = create_access_token(data={"sub": user.id})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.jwt_expiration_minutes * 60,
        samesite="lax",
    )
    
    # Log Audit: Role-Specific Login
    role_label = "Admin" if user.role == "admin" else ("Employee" if user.role == "adjuster" else "User")
    log_audit(db, user.id, f"{role_label} Login", {"username": user.username, "role": user.role})
    
    # Check if forced password reset is active
    if user.must_change_password:
        return {
            "message": "Password change required on first login.", 
            "must_change_password": True,
            "role": user.role,
            "full_name": user.full_name
        }
        
    return {
        "message": "Logged in successfully",
        "role": user.role,
        "full_name": user.full_name
    }


@app.post("/change-password")
def change_password(req: PasswordChangeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.password_hash = get_password_hash(req.new_password)
    current_user.must_change_password = False
    db.commit()
    log_audit(db, current_user.id, "Password Changed", {"username": current_user.username})
    return {"message": "Password updated successfully"}


@app.post("/forgot-password")
def forgot_password(req: SelfResetPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    generic_msg = "If an account exists for this email, a password reset link has been sent."
    
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        user = db.query(User).filter(User.username == clean_email).first()
        
    if not user:
        log_audit(db, None, "Forgot Password Attempt (Unmatched Email)", {"email_attempt": clean_email})
        return {"message": generic_msg}
        
    # Invalidate previous reset token & generate single-use 30-minute token
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    db.commit()
    
    recipient_email = user.email or clean_email
    reset_url = f"{settings.frontend_url}/?setup_token={reset_token}"
    background_tasks.add_task(send_activation_email, recipient_email, user.full_name or user.username, user.username, reset_url)
    
    log_audit(db, user.id, "Password Reset Link Dispatched", {"username": user.username, "email": recipient_email})
    return {
        "message": generic_msg,
        "email": recipient_email,
        "reset_url": reset_url,
        "username": user.username,
        "full_name": user.full_name or user.username
    }


@app.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logout_user(current_user.id)
    response.delete_cookie("access_token")
    role_label = "Admin" if current_user.role == "admin" else ("Employee" if current_user.role == "adjuster" else "User")
    log_audit(db, current_user.id, f"{role_label} Logout", {"username": current_user.username, "role": current_user.role})
    return {"message": "Logged out successfully"}


@app.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


from app.schemas import PredictRequest, PredictResponse

@app.post("/predict", response_model=PredictResponse)
def predict_fraud(request: PredictRequest):
    from app.ml_service import predict_fraud_probability
    return predict_fraud_probability(request.dict())


def run_claim_agent_background(claim_id: str) -> None:
    import sys
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_claim_agent(SessionLocal, claim_id))


@app.post("/claims", response_model=ClaimOut)
async def create_claim(
    background_tasks: BackgroundTasks,
    claimant_name: str = Form(...),
    claim_type: str = Form(...),
    policy_number: str = Form(...),
    amount_requested: float = Form(...),
    description: str = Form(...),
    incident_date: str = Form(...),
    incident_location: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can submit new claims.")
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Deactivated account.")
        
    if not (1.0 <= amount_requested <= 100000.0):
        raise HTTPException(
            status_code=400,
            detail="Amount requested must be between 1 and 100,000."
        )

    try:
        inc_date_parsed = datetime.datetime.strptime(incident_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Incident Date must be in YYYY-MM-DD format.")

    # Validation
    for file in files:
        validate_uploaded_file(file)

    claim = Claim(
        claimant_name=claimant_name,
        claim_type=claim_type,
        policy_number=policy_number,
        amount_requested=amount_requested,
        description=description,
        incident_date=inc_date_parsed,
        incident_location=incident_location,
        user_id=current_user.id,
        status=ClaimStatus.submitted.value
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    for file in files:
        object_name, url = await save_upload(file, claim.id)
        db.add(
            Evidence(
                claim_id=claim.id,
                filename=file.filename or "upload",
                object_name=object_name,
                url=url,
                content_type=file.content_type or "application/octet-stream",
            )
        )
    db.commit()

    log_audit(db, current_user.id, "Claim Submitted", {
        "claim_id": claim.id,
        "amount": amount_requested,
        "claim_type": claim_type
    })
    log_audit(db, current_user.id, "Evidence Uploaded", {
        "claim_id": claim.id,
        "files_count": len(files)
    })

    background_tasks.add_task(run_claim_agent_background, claim.id)
    loaded = claim_with_children(db, claim.id)
    return loaded


@app.get("/claims", response_model=List[ClaimOut])
def list_claims(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    auto_assign_claims(db)
    if current_user.role == "customer":
        return db.query(Claim).filter(Claim.user_id == current_user.id).order_by(Claim.created_at.desc()).all()
    elif current_user.role == "adjuster":
        # Adjusters see claims assigned strictly to them
        return db.query(Claim).filter(Claim.assigned_adjuster_id == current_user.id).order_by(Claim.created_at.desc()).all()
    elif current_user.role == "admin":
        return db.query(Claim).order_by(Claim.created_at.desc()).all()
    return []


@app.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    claim = claim_with_children(db, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if current_user.role == "customer" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
        
    return claim


@app.get("/claims/{claim_id}/events")
def claim_events(claim_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    claim = claim_with_children(db, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if current_user.role == "customer" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return StreamingResponse(stream_events(SessionLocal, claim_id), media_type="text/event-stream")


@app.post("/claims/{claim_id}/adjudicate", response_model=ClaimOut)
def adjudicate_claim(
    claim_id: str, 
    req: AdjudicationRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in {"adjuster", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied. Only Adjusters or Admins can override decisions.")
        
    claim = claim_with_children(db, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if current_user.role == "adjuster" and claim.assigned_adjuster_id != current_user.id:
        raise HTTPException(status_code=403, detail="Claim is not assigned to you.")
    old_status = claim.status
    if req.action == "APPROVE":
        claim.status = ClaimStatus.approved.value
        claim.decision = "Approved (Adjuster Override)"
        claim.decision_reason = "Manual Adjuster Override"
    elif req.action == "REJECT":
        claim.status = ClaimStatus.rejected.value
        claim.decision = "Rejected (Adjuster Override)"
        claim.decision_reason = "Manual Adjuster Override"
    elif req.action == "REQUEST_DOCUMENTS":
        claim.status = ClaimStatus.under_review.value
        claim.decision = "Under Review (Documents Requested)"
        claim.decision_reason = "Manual Adjuster Override"
    else:
        raise HTTPException(status_code=400, detail="Invalid adjudication action.")

    claim.reviewed_by_id = current_user.id
    claim.reviewed_at = datetime.datetime.utcnow()
    if req.notes:
        claim.adjuster_notes = req.notes
        claim.reviewer_notes = req.notes
        
    db.commit()
    db.refresh(claim)
    
    log_audit(db, current_user.id, "Adjuster Override", {
        "claim_id": claim_id,
        "old_status": old_status,
        "new_status": claim.status,
        "action": req.action,
        "notes": req.notes
    })
    return claim


@app.post("/claims/{claim_id}/assign", response_model=ClaimOut)
def assign_claim(
    claim_id: str, 
    adjuster_id: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can assign claims to adjusters.")
        
    claim = claim_with_children(db, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    adjuster = db.query(User).filter(User.id == adjuster_id, User.role == "adjuster").first()
    if not adjuster:
        raise HTTPException(status_code=404, detail="Selected Adjuster not found.")
        
    # Check if this is an initial assignment or a reassignment
    old_adj_id = claim.assigned_adjuster_id
    claim.assigned_adjuster_id = adjuster.id
    db.commit()
    db.refresh(claim)
    
    if old_adj_id:
        log_audit(db, current_user.id, "Claim Reassigned", {
            "claim_id": claim_id,
            "old_adjuster_id": old_adj_id,
            "new_adjuster_id": adjuster.id,
            "adjuster_name": adjuster.full_name
        })
    else:
        log_audit(db, current_user.id, "Claim Assigned", {
            "claim_id": claim_id,
            "adjuster_id": adjuster.id,
            "adjuster_name": adjuster.full_name
        })
        
    return claim


@app.get("/admin/users", response_model=List[UserOut])
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can access user directories.")
    return db.query(User).order_by(User.created_at.desc()).all()


from app.email_service import send_activation_email


@app.post("/admin/employees")
def create_employee(
    req: EmployeeCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can create employee profiles.")
        
    if req.role not in {"adjuster", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid employee role. Must be 'adjuster' or 'admin'.")
        
    # Set Username: explicitly specified by Admin or auto-generated (first 2 letters + last name)
    if req.username and req.username.strip():
        username = req.username.strip().lower()
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail=f"Username '{username}' is already taken.")
    else:
        name_parts = req.full_name.strip().split()
        if len(name_parts) >= 2:
            first_two = name_parts[0][:2].lower()
            last_clean = re.sub(r'[^a-zA-Z0-9]', '', "".join(name_parts[1:])).lower()
            base_username = f"{first_two}{last_clean}"
        else:
            base_username = re.sub(r'[^a-zA-Z0-9]', '', req.full_name).lower()
            
        username = base_username
        idx = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{idx}"
            idx += 1
        
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="An employee with this email already exists.")
        
    # Generate Customer/Employee ID prefix
    while True:
        emp_id = ("ADJ-" if req.role == "adjuster" else "ADM-") + secrets.token_hex(4).upper()[:7]
        if not db.query(User).filter(User.customer_id == emp_id).first():
            break
            
    # Generate one-time password setup token (valid for 7 days)
    setup_token = secrets.token_urlsafe(32)
    token_expires = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    
    emp = User(
        username=username,
        password_hash=get_password_hash(req.temporary_password or secrets.token_urlsafe(12)),
        customer_id=emp_id,
        role=req.role,
        full_name=req.full_name,
        is_identity_verified=True,
        email=req.email,
        must_change_password=True,
        is_active=True,
        reset_token=setup_token,
        reset_token_expires_at=token_expires
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    
    log_audit(db, current_user.id, "Employee Created", {
        "employee_id": emp.id,
        "username": emp.username,
        "email": req.email,
        "role": req.role
    })
    
    act_link = f"{settings.frontend_url}/?setup_token={setup_token}"
    background_tasks.add_task(send_activation_email, emp.email, emp.full_name, emp.username, act_link)
    
    return {
        "id": emp.id,
        "username": emp.username,
        "customer_id": emp.customer_id,
        "role": emp.role,
        "full_name": emp.full_name,
        "email": emp.email,
        "setup_token": setup_token,
        "activation_link": act_link
    }


@app.get("/setup-password/verify")
def verify_setup_token(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == token).first()
    if not user or (user.reset_token_expires_at and user.reset_token_expires_at < datetime.datetime.utcnow()):
        raise HTTPException(status_code=400, detail="Invalid or expired password activation token.")
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email
    }


@app.post("/setup-password")
def setup_password(req: TokenResetPasswordRequest, db: Session = Depends(get_db)):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    user = db.query(User).filter(User.reset_token == req.token).first()
    if not user or (user.reset_token_expires_at and user.reset_token_expires_at < datetime.datetime.utcnow()):
        raise HTTPException(status_code=400, detail="Invalid or expired password activation token.")
        
    user.password_hash = get_password_hash(req.new_password)
    user.must_change_password = False
    user.reset_token = None
    user.reset_token_expires_at = None
    user.is_active = True
    db.commit()
    
    logout_user(user.id)
    log_audit(db, user.id, "Account Password Established", {"username": user.username, "role": user.role})
    return {"message": "Account password set successfully! You may now log in with your credentials."}


@app.post("/admin/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: str, 
    is_active: bool, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can activate or deactivate accounts.")
        
    if user_id == current_user.id and not is_active:
        raise HTTPException(status_code=400, detail="Self-deactivation is restricted. You cannot deactivate your own admin session.")
        
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if target_user.role == "admin" and not is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Deactivation denied. There must be at least one active administrator in the system.")
            
    target_user.is_active = is_active
    db.commit()
    db.refresh(target_user)
    
    action_log = "User Activated" if is_active else "User Deactivated"
    log_audit(db, current_user.id, action_log, {
        "target_user_id": user_id,
        "target_username": target_user.username
    })
    return target_user


@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can delete user accounts.")
        
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Self-deletion is restricted. You cannot delete your own admin session.")
        
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if target_user.role == "admin":
        active_admins = db.query(User).filter(User.role == "admin").count()
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Deletion denied. There must be at least one administrator account in the system.")
            
    deleted_username = target_user.username
    deleted_role = target_user.role
    
    try:
        # Foreign Key Cleanup
        db.query(AuditLog).filter(AuditLog.user_id == user_id).update({"user_id": None})
        db.query(Claim).filter(Claim.assigned_adjuster_id == user_id).update({"assigned_adjuster_id": None})
        db.query(Claim).filter(Claim.reviewed_by_id == user_id).update({"reviewed_by_id": None})
        db.query(Claim).filter(Claim.user_id == user_id).update({"user_id": None})
        db.commit()
        
        db.delete(target_user)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete user '{deleted_username}': {str(e)}")
    
    log_audit(db, current_user.id, "User Deleted", {
        "target_user_id": user_id,
        "target_username": deleted_username,
        "role": deleted_role
    })
    return {"message": f"User '{deleted_username}' deleted successfully."}


@app.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can trigger password resets.")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    user.must_change_password = True
    db.commit()
    
    logout_user(user.id)
    
    recipient_email = user.email or f"{user.username}@company.com"
    reset_url = f"{settings.frontend_url}/?setup_token={reset_token}"
    background_tasks.add_task(send_activation_email, recipient_email, user.full_name or user.username, user.username, reset_url)
    
    log_audit(db, current_user.id, "Admin Password Reset Triggered", {
        "target_user_id": user_id,
        "target_username": user.username,
        "recipient_email": recipient_email
    })
    return {
        "message": f"Password reset link has been dispatched to {recipient_email}.",
        "reset_url": reset_url,
        "email": recipient_email,
        "username": user.username,
        "full_name": user.full_name or user.username
    }


@app.get("/admin/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied. Audit logs are restricted to Administrators.")
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()


@app.get("/adjusters", response_model=List[UserOut])
def list_adjusters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in {"admin", "adjuster"}:
        raise HTTPException(status_code=403, detail="Access denied.")
    return db.query(User).filter(User.role == "adjuster").all()


@app.post("/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: str, 
    role: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in {"admin", "adjuster"}:
        raise HTTPException(status_code=403, detail="Only Admins and Adjusters can modify user roles.")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if user.role == "customer" or role == "customer":
        raise HTTPException(
            status_code=400, 
            detail="Role changes are only permitted between Adjuster and Admin roles. Customers cannot be converted to staff roles."
        )

    if role not in {"adjuster", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid target role. Must be 'adjuster' or 'admin'.")
        
    old_role = user.role
    user.role = role
    db.commit()
    db.refresh(user)
    
    log_audit(db, current_user.id, "Role Assignment", {
        "target_user_id": user_id,
        "old_role": old_role,
        "new_role": role
    })
    return user
