from sqlalchemy import text
from app.database import engine

def check_events():
    with engine.connect() as conn:
        print("--- Latest claims ---")
        claims = conn.execute(text("SELECT id, claimant_name, status, fraud_risk_score FROM claims ORDER BY created_at DESC LIMIT 5")).fetchall()
        for c in claims:
            print(f"Claim ID: {c[0]}, Name: {c[1]}, Status: {c[2]}, Risk: {c[3]}")
            
        print("\n--- Events for latest claim ---")
        if claims:
            latest_id = claims[0][0]
            events = conn.execute(text("SELECT step, message, status, created_at FROM agent_events WHERE claim_id = :id ORDER BY created_at ASC"), {"id": latest_id}).fetchall()
            for e in events:
                print(f"[{e[2].upper()}] {e[0]}: {repr(e[1])} ({e[3]})")

if __name__ == "__main__":
    check_events()
