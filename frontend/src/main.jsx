import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { 
  Activity, 
  FileImage, 
  Play, 
  ShieldCheck, 
  UploadCloud, 
  LogOut, 
  User as UserIcon, 
  FileText, 
  Users, 
  List, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Plus, 
  Calendar, 
  MapPin, 
  ArrowRight,
  Clock,
  Key,
  Mail,
  Search
} from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

function formatEmail(email) {
  if (!email) return '-';
  return email.replace(/\.dup/gi, '').replace(/(@[^\s@]+)@company\.com$/i, '$1');
}

function App() {
  const [user, setUser] = useState(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false);
  
  const [claims, setClaims] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [authError, setAuthError] = useState('');
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [loginRoleTab, setLoginRoleTab] = useState('customer'); // 'customer', 'adjuster', 'admin'
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  function handleRoleTabSwitch(tab) {
    setLoginRoleTab(tab);
    setIsLoginMode(true);
    setAuthError('');
    setLoginUsername('');
    setLoginPassword('');
  }
  
  // Forced password reset state
  const [mustResetPassword, setMustResetPassword] = useState(false);
  const [resetPwdValue, setResetPwdValue] = useState('');
  const [resetPwdSuccess, setResetPwdSuccess] = useState('');
  
  // Admin Tabs & Filters
  const [currentTab, setCurrentTab] = useState('claims'); // 'claims', 'users', 'audit', 'analytics'
  const [filterCustId, setFilterCustId] = useState('');
  const [filterClaimantName, setFilterClaimantName] = useState('');
  const [filterClaimId, setFilterClaimId] = useState('');
  const [filterAdjusterId, setFilterAdjusterId] = useState('');
  const [showFileClaim, setShowFileClaim] = useState(false);
  const [registrationFileName, setRegistrationFileName] = useState('');
  const [claimFileNames, setClaimFileNames] = useState([]);
  
  // Employee Creation & Admin Management State
  const [adjusters, setAdjusters] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [assigneeId, setAssigneeId] = useState('');
  const [adjudicationAction, setAdjudicationAction] = useState('APPROVE');
  const [adjudicationNotes, setAdjudicationNotes] = useState('');
  
  // Create Employee Form State
  const [empName, setEmpName] = useState('');
  const [empEmail, setEmpEmail] = useState('');
  const [empUsername, setEmpUsername] = useState('');
  const [empRole, setEmpRole] = useState('adjuster');
  const [empSuccessMsg, setEmpSuccessMsg] = useState('');

  function handleEmpNameChange(val) {
    setEmpName(val);
    const parts = val.trim().split(/\s+/);
    if (parts.length >= 2) {
      const firstTwo = parts[0].slice(0, 2).toLowerCase();
      const lastClean = parts.slice(1).join('').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
      setEmpUsername(`${firstTwo}${lastClean}`);
    } else if (parts.length === 1 && parts[0]) {
      setEmpUsername(parts[0].replace(/[^a-zA-Z0-9]/g, '').toLowerCase());
    }
  }
  
  // Password Reset Alert Modal
  const [resetAlertMsg, setResetAlertMsg] = useState('');

  // Self-Service Password Reset State (All Roles)
  const [isForgotPasswordMode, setIsForgotPasswordMode] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotPwdMsg, setForgotPwdMsg] = useState('');
  const [forgotPwdSuccess, setForgotPwdSuccess] = useState('');
  const [forgotResetInfo, setForgotResetInfo] = useState(null);
  const [showSelfChangePwdModal, setShowSelfChangePwdModal] = useState(false);

  const selected = useMemo(
    () => claims.find((claim) => claim.id === selectedId),
    [claims, selectedId],
  );

  const filteredAdminClaims = useMemo(() => {
    return claims.filter((c) => {
      if (filterAdjusterId) {
        const targetAdj = allUsers.find(u => u.id === filterAdjusterId);
        const targetUsername = targetAdj?.username?.toLowerCase();
        const targetName = targetAdj?.full_name?.toLowerCase();
        const isMatch = (
          c.assigned_adjuster_id === filterAdjusterId ||
          c.assigned_adjuster?.id === filterAdjusterId ||
          (targetUsername && c.assigned_adjuster?.username?.toLowerCase() === targetUsername) ||
          (targetName && c.assigned_adjuster?.full_name?.toLowerCase() === targetName)
        );
        if (!isMatch) return false;
      }
      if (filterCustId.trim()) {
        const qCust = filterCustId.toLowerCase().trim();
        const userCustId = c.user?.customer_id?.toLowerCase() || '';
        const userId = c.user_id?.toLowerCase() || '';
        const adjCustId = c.assigned_adjuster?.customer_id?.toLowerCase() || '';
        if (!userCustId.includes(qCust) && !userId.includes(qCust) && !adjCustId.includes(qCust)) return false;
      }
      if (filterClaimantName.trim()) {
        const qName = filterClaimantName.toLowerCase().trim();
        const name = c.claimant_name?.toLowerCase() || '';
        const username = c.user?.username?.toLowerCase() || '';
        const fullName = c.user?.full_name?.toLowerCase() || '';
        const adjName = c.assigned_adjuster?.full_name?.toLowerCase() || '';
        const adjUser = c.assigned_adjuster?.username?.toLowerCase() || '';
        if (!name.includes(qName) && !username.includes(qName) && !fullName.includes(qName) && !adjName.includes(qName) && !adjUser.includes(qName)) return false;
      }
      if (filterClaimId.trim()) {
        const qClaim = filterClaimId.toLowerCase().trim();
        const id = c.id?.toLowerCase() || '';
        const policy = c.policy_number?.toLowerCase() || '';
        if (!id.includes(qClaim) && !policy.includes(qClaim)) return false;
      }
      return true;
    });
  }, [claims, filterAdjusterId, filterCustId, filterClaimantName, filterClaimId]);

  // Activation / Setup Token Link State
  const [tokenFromUrl, setTokenFromUrl] = useState('');
  const [tokenUserInfo, setTokenUserInfo] = useState(null);
  const [tokenNewPassword, setTokenNewPassword] = useState('');
  const [tokenError, setTokenError] = useState('');
  const [tokenSuccess, setTokenSuccess] = useState('');
  const [createdEmployeeInfo, setCreatedEmployeeInfo] = useState(null);

  async function checkAuth() {
    try {
      const response = await fetch(`${API_BASE}/me`, {credentials: 'include'});
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        if (data.must_change_password) {
          setMustResetPassword(true);
        }
      } else {
        setUser(null);
      }
    } catch (e) {
      setUser(null);
    } finally {
      setIsAuthChecking(false);
    }
  }

  async function verifyToken(t) {
    try {
      const res = await fetch(`${API_BASE}/setup-password/verify?token=${t}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Invalid or expired password activation link.');
      }
      const data = await res.json();
      setTokenUserInfo(data);
      if (data.role) {
        setLoginRoleTab(data.role);
      }
    } catch (e) {
      setTokenError(e.message);
    }
  }

  async function handleTokenPasswordSetup(e) {
    e.preventDefault();
    setTokenError('');
    setTokenSuccess('');
    try {
      const res = await fetch(`${API_BASE}/setup-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenFromUrl, new_password: tokenNewPassword })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Password setup failed.');
      }
      setTokenSuccess('Password set successfully! Redirecting to login...');
      setTimeout(() => {
        if (tokenUserInfo && tokenUserInfo.role) {
          setLoginRoleTab(tokenUserInfo.role);
        }
        window.history.replaceState({}, document.title, window.location.pathname);
        setTokenFromUrl('');
        setTokenUserInfo(null);
      }, 2000);
    } catch (err) {
      setTokenError(err.message);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('setup_token') || params.get('token');
    if (token) {
      setTokenFromUrl(token);
      verifyToken(token);
    }
    checkAuth();
  }, []);

  async function loadClaims() {
    try {
      const response = await fetch(`${API_BASE}/claims`, {credentials: 'include'});
      if (!response.ok) throw new Error(`Claims API returned ${response.status}`);
      const data = await response.json();
      setClaims(data);
      if (data.length && !selectedId) {
        setSelectedId(data[0].id);
      }
      setError('');
    } catch (reason) {
      setError(reason.message || 'Unable to load claims.');
    }
  }

  async function loadAdjusters() {
    try {
      const response = await fetch(`${API_BASE}/adjusters`, {credentials: 'include'});
      if (response.ok) {
        const data = await response.json();
        setAdjusters(data);
      }
    } catch (e) {
      console.error("Failed to load adjusters", e);
    }
  }

  async function loadAuditLogs() {
    try {
      const response = await fetch(`${API_BASE}/admin/audit-logs`, {credentials: 'include'});
      if (response.ok) {
        const data = await response.json();
        setAuditLogs(data);
      }
    } catch (e) {
      console.error("Failed to load audit logs", e);
    }
  }

  async function loadAllUsers() {
    try {
      const response = await fetch(`${API_BASE}/admin/users`, {credentials: 'include'});
      if (response.ok) {
        const data = await response.json();
        setAllUsers(data);
      }
    } catch (e) {
      console.error("Failed to load users directory", e);
    }
  }

  useEffect(() => {
    if (user && !mustResetPassword) {
      loadClaims();
      if (user.role === 'admin') {
        loadAdjusters();
        loadAuditLogs();
        loadAllUsers();
      } else if (user.role === 'adjuster') {
        loadAdjusters();
      }
    }
  }, [user, mustResetPassword]);

  useEffect(() => {
    if (!selectedId || !user || mustResetPassword) return undefined;
    
    const curClaim = claims.find(c => c.id === selectedId);
    setEvents(curClaim?.events || []);

    const source = new EventSource(`${API_BASE}/claims/${selectedId}/events`, { withCredentials: true });
    
    source.addEventListener('agent_step', (message) => {
      try {
        const next = JSON.parse(message.data);
        setEvents((current) => (current.some((event) => event.id === next.id) ? current : [...current, next]));
      } catch {
        setEvents((current) => [
          ...current,
          { id: crypto.randomUUID(), step: 'agent', message: message.data, status: 'done' },
        ]);
      }
    });

    source.addEventListener('done', () => {
      source.close();
      loadClaims();
      if (user.role === 'admin') {
        loadAuditLogs();
      }
    });

    source.addEventListener('error', () => {
      source.close();
    });

    return () => source.close();
  }, [selectedId, user, mustResetPassword]);

  async function submitClaim(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);

    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/claims`, { 
        method: 'POST', 
        body: formData,
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Claim submission failed');
      }
      const claim = await response.json();
      form.reset();
      setClaims((current) => [claim, ...current]);
      setSelectedId(claim.id);
      setShowFileClaim(false);
      setClaimFileNames([]);
    } catch (reason) {
      setError(reason.message || 'Claim submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAdjudicate(event) {
    event.preventDefault();
    setError('');
    try {
      const response = await fetch(`${API_BASE}/claims/${selectedId}/adjudicate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: adjudicationAction,
          notes: adjudicationNotes
        }),
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Override failed');
      }
      const updated = await response.json();
      setClaims((current) => current.map(c => c.id === updated.id ? updated : c));
      setAdjudicationNotes('');
      if (user.role === 'admin') {
        loadAuditLogs();
      }
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleAssign(event) {
    event.preventDefault();
    if (!assigneeId) return;
    setError('');
    try {
      const response = await fetch(`${API_BASE}/claims/${selectedId}/assign?adjuster_id=${assigneeId}`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Assignment failed');
      }
      const updated = await response.json();
      setClaims((current) => current.map(c => c.id === updated.id ? updated : c));
      setAssigneeId('');
      loadAuditLogs();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleCreateEmployee(event) {
    event.preventDefault();
    setError('');
    setEmpSuccessMsg('');
    setCreatedEmployeeInfo(null);
    try {
      const response = await fetch(`${API_BASE}/admin/employees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: empName,
          email: empEmail,
          role: empRole,
          username: empUsername
        }),
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Failed to create employee profile.');
      }
      const data = await response.json();
      const roleLabel = empRole === 'adjuster' ? 'Adjuster' : 'Admin';
      setEmpSuccessMsg(`✅ Successfully provisioned ${roleLabel} profile for ${empName}. Username: "${data.username}". Password setup link sent to ${empEmail}.`);
      setEmpName('');
      setEmpEmail('');
      setEmpUsername('');
      loadAllUsers();
      loadAuditLogs();
    } catch (e) {
      setError(e.message);
    }
  }

  const [userDirBanner, setUserDirBanner] = useState({ text: '', type: '' });

  async function handleDeleteUser(userId, username) {
    if (!confirm(`Are you sure you want to permanently delete account "${username}"?`)) return;
    setError('');
    try {
      const response = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Failed to delete user account.');
      }
      setUserDirBanner({ text: `User account "${username}" deleted successfully.`, type: 'success' });
      loadAllUsers();
      loadAuditLogs();
    } catch (e) {
      setError(e.message);
      setUserDirBanner({ text: `Delete failed: ${e.message}`, type: 'error' });
    }
  }

  async function handleResetPassword(userId, username) {
    setError('');
    try {
      const response = await fetch(`${API_BASE}/admin/users/${userId}/reset-password`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Password reset request failed.');
      }
      const data = await response.json();
      setUserDirBanner({ 
        text: `Password reset link dispatched for account "${username}" (${formatEmail(data.email)}).`, 
        type: 'success',
        resetUrl: data.reset_url
      });
      loadAuditLogs();
    } catch (e) {
      setError(e.message);
      setUserDirBanner({ text: `Reset Password failed: ${e.message}`, type: 'error' });
    }
  }

  async function handleUserRoleUpdate(userId, newRole) {
    setError('');
    const targetUser = allUsers.find(u => u.id === userId);
    if (targetUser && (targetUser.username === 'admin' || targetUser.customer_id === 'ADM-SYSTEM')) {
      setUserDirBanner({ text: 'Role modification denied: The primary System Administrator account ("admin") role cannot be changed.', type: 'error' });
      loadAllUsers();
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/admin/users/${userId}/role?role=${newRole}`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Role update failed');
      }
      setUserDirBanner({ text: `User role updated to ${newRole.toUpperCase()} successfully.`, type: 'success' });
      loadAllUsers();
      loadAuditLogs();
    } catch (e) {
      setError(e.message);
      setUserDirBanner({ text: `Role update failed: ${e.message}`, type: 'error' });
      loadAllUsers();
    }
  }

  async function handleForcedPasswordChange(event) {
    event.preventDefault();
    setError('');
    setResetPwdSuccess('');
    try {
      const response = await fetch(`${API_BASE}/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: resetPwdValue }),
        credentials: 'include'
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Failed to update password.');
      }
      setResetPwdSuccess('Password changed successfully! Redirecting...');
      setTimeout(() => {
        setMustResetPassword(false);
        checkAuth();
      }, 1500);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleSelfForgotPassword(event) {
    event.preventDefault();
    setForgotPwdMsg('');
    setForgotPwdSuccess('');
    setForgotResetInfo(null);
    try {
      const response = await fetch(`${API_BASE}/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail })
      });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Password reset request failed.');
      }
      const data = await response.json();
      if (data.reset_url) {
        setForgotResetInfo(data);
      }
      setForgotPwdSuccess(data.message || 'If an account exists for this email, a password reset link has been sent.');
    } catch (e) {
      setForgotPwdMsg(e.message);
    }
  }

  async function handleAuth(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    
    setAuthError('');
    setIsAuthSubmitting(true);
    try {
      const endpoint = isLoginMode ? '/login' : '/register';
      const options = {
        method: 'POST',
        credentials: 'include'
      };
      
      if (isLoginMode) {
        options.headers = { 'Content-Type': 'application/json' };
        const payload = Object.fromEntries(formData);
        payload.expected_role = loginRoleTab;
        options.body = JSON.stringify(payload);
      } else {
        options.body = formData;
      }
      
      const response = await fetch(`${API_BASE}${endpoint}`, { ...options });
      if (!response.ok) {
        const resData = await response.json();
        throw new Error(resData.detail || 'Authentication failed');
      }
      
      const resData = await response.json();
      setLoginUsername('');
      setLoginPassword('');
      if (!isLoginMode) {
        setIsLoginMode(true);
        setAuthError('Registration successful. Please log in.');
      } else {
        if (resData.must_change_password) {
          setMustResetPassword(true);
        } else {
          checkAuth();
        }
      }
    } catch (e) {
      setAuthError(e.message);
    } finally {
      setIsAuthSubmitting(false);
    }
  }

  async function logout() {
    try {
      await fetch(`${API_BASE}/logout`, { method: 'POST', credentials: 'include' });
    } catch (e) {
      console.error(e);
    }
    setUser(null);
    setClaims([]);
    setSelectedId(null);
    setEvents([]);
    setMustResetPassword(false);
  }

  if (isAuthChecking) {
    return <main className="shell"><div className="loading-container">Loading terminal...</div></main>;
  }

  // Render Token Password Setup Screen (from email activation link)
  if (tokenFromUrl) {
    return (
      <main className="shell auth-shell">
        <div style={{ maxWidth: '460px', margin: '3rem auto', width: '100%' }}>
          <div className="brand-header">
            <Key size={40} className="brand-icon" />
            <h1>Enterprise Account Setup</h1>
            <p className="brand-sub">Establish Corporate Password via One-Time Token</p>
          </div>
          <form className="panel claim-form" onSubmit={handleTokenPasswordSetup}>
            <h2>Complete Profile Setup</h2>
            {tokenError && <div className="error-banner">{tokenError}</div>}
            {tokenSuccess && <div className="status-pill" style={{ display: 'block', width: '100%', marginBottom: '12px', background: '#dcfce7', color: '#166534' }}>{tokenSuccess}</div>}
            
            {tokenUserInfo && (
              <div style={{ background: 'var(--mono-surface-dark)', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', marginBottom: '14px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div><strong>Employee Name:</strong> {tokenUserInfo.full_name}</div>
                <div><strong>Generated Username:</strong> <code style={{ background: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>{tokenUserInfo.username}</code></div>
                <div><strong>Role:</strong> {tokenUserInfo.role?.toUpperCase()}</div>
                <div><strong>Email:</strong> {tokenUserInfo.email}</div>
              </div>
            )}

            <div className="input-group">
              <label>Set Permanent Corporate Password</label>
              <input 
                type="password"
                placeholder="••••••••" 
                value={tokenNewPassword}
                onChange={(e) => setTokenNewPassword(e.target.value)}
                required 
              />
            </div>

            <button type="submit" disabled={!tokenUserInfo}>Save Password & Activate Account</button>
          </form>
        </div>
      </main>
    );
  }

  // Render password change screen if forced change is active
  if (mustResetPassword) {
    return (
      <main className="shell auth-shell">
        <div style={{ maxWidth: '400px', margin: '4rem auto', width: '100%' }}>
          <div className="brand-header">
            <Key size={40} className="brand-icon" />
            <h1>Force Reset Password</h1>
            <p className="brand-sub">Security Policy Constraint Active</p>
          </div>
          <form className="panel claim-form" onSubmit={handleForcedPasswordChange}>
            <h2>Establish New Password</h2>
            {error && <div className="error-banner">{error}</div>}
            {resetPwdSuccess && <div className="status-pill" style={{ display: 'block', width: '100%', marginBottom: '12px' }}>{resetPwdSuccess}</div>}
            <div className="input-group">
              <label>Enter New Password</label>
              <input 
                type="password" 
                placeholder="••••••••" 
                value={resetPwdValue} 
                onChange={(e) => setResetPwdValue(e.target.value)} 
                required 
              />
            </div>
            <button type="submit">Update Password</button>
            <button type="button" onClick={logout} style={{ marginTop: '8px', background: 'var(--mono-surface-dark)' }}>Cancel & Log Out</button>
          </form>
        </div>
      </main>
    );
  }

  if (isForgotPasswordMode) {
    return (
      <main className="shell auth-shell">
        <div style={{ maxWidth: '460px', margin: '3rem auto', width: '100%' }}>
          <div className="brand-header">
            <Key size={40} className="brand-icon" />
            <h1>Self-Service Password Reset</h1>
            <p className="brand-sub">Request Password Reset Link via Registered Email</p>
          </div>
          <form className="panel claim-form" onSubmit={handleSelfForgotPassword}>
            <h2>Reset Account Password</h2>
            {forgotPwdMsg && <div className="error-banner">{forgotPwdMsg}</div>}
            {forgotPwdSuccess && <div className="status-pill" style={{ display: 'block', width: '100%', marginBottom: '12px', background: '#dcfce7', color: '#166534' }}>{forgotPwdSuccess}</div>}
            
            

            <div className="input-group">
              <label>Registered Email Address</label>
              <input 
                type="email"
                placeholder="name@company.com" 
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                required 
              />
            </div>

            <button type="submit">Send Password Reset Link</button>
            <p style={{marginTop: '1.2rem', textAlign: 'center', fontSize: '13px'}}>
              <a href="#" onClick={(e) => { e.preventDefault(); setIsForgotPasswordMode(false); }}>
                ← Back to Login
              </a>
            </p>
          </form>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="shell auth-shell">
        <div style={{ maxWidth: '460px', margin: '3rem auto', width: '100%' }}>
          <div className="brand-header">
            <ShieldCheck size={40} className="brand-icon" />
            <h1>Claims Guard AI</h1>
            <p className="brand-sub">Enterprise Insurance Verification Platform</p>
          </div>

          {/* Dedicated Login Portal Selection Tabs */}
          {isLoginMode && (
            <div style={{ display: 'flex', gap: '4px', marginBottom: '14px', background: 'var(--mono-surface-dark)', padding: '4px', borderRadius: '6px' }}>
              <button 
                type="button" 
                onClick={() => handleRoleTabSwitch('customer')}
                style={{ 
                  flex: 1, 
                  padding: '8px 4px', 
                  fontSize: '11px', 
                  fontWeight: 'bold', 
                  border: 'none', 
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: loginRoleTab === 'customer' ? 'var(--mono-surface)' : 'transparent',
                  color: loginRoleTab === 'customer' ? 'var(--mono-text)' : 'var(--mono-text-light)',
                  boxShadow: loginRoleTab === 'customer' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                👥 Policyholder
              </button>
              <button 
                type="button" 
                onClick={() => handleRoleTabSwitch('adjuster')}
                style={{ 
                  flex: 1, 
                  padding: '8px 4px', 
                  fontSize: '11px', 
                  fontWeight: 'bold', 
                  border: 'none', 
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: loginRoleTab === 'adjuster' ? 'var(--mono-surface)' : 'transparent',
                  color: loginRoleTab === 'adjuster' ? 'var(--mono-text)' : 'var(--mono-text-light)',
                  boxShadow: loginRoleTab === 'adjuster' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                ⚖️ Adjuster
              </button>
              <button 
                type="button" 
                onClick={() => handleRoleTabSwitch('admin')}
                style={{ 
                  flex: 1, 
                  padding: '8px 4px', 
                  fontSize: '11px', 
                  fontWeight: 'bold', 
                  border: 'none', 
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: loginRoleTab === 'admin' ? 'var(--mono-surface)' : 'transparent',
                  color: loginRoleTab === 'admin' ? 'var(--mono-text)' : 'var(--mono-text-light)',
                  boxShadow: loginRoleTab === 'admin' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                🛡️ Admin
              </button>
            </div>
          )}
          
          <form className="panel claim-form" key={loginRoleTab + '-' + (isLoginMode ? 'login' : 'register')} onSubmit={handleAuth} autoComplete="off">
            <h2>
              {isLoginMode 
                ? (loginRoleTab === 'adjuster' ? '⚖️ Claims Adjuster Login Portal' : loginRoleTab === 'admin' ? '🛡️ Administrator Executive Portal' : '👥 Policyholder Customer Login')
                : 'Register Customer Profile'
              }
            </h2>
            {authError && <div className="error-banner">{authError}</div>}
            
            
            <div className="input-group">
              <label>Username</label>
              <input 
                name="username" 
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                autoComplete="off"
                placeholder={
                  isLoginMode 
                    ? (loginRoleTab === 'adjuster' ? 'e.g. adjuster_user' : loginRoleTab === 'admin' ? 'e.g. admin' : 'Enter username') 
                    : 'Enter username'
                } 
                required 
              />
            </div>
            
            {!isLoginMode && (
              <>
                <div className="input-group">
                  <label>Full Name</label>
                  <input name="full_name" placeholder="John Doe" required />
                </div>
                <div className="input-group">
                  <label>Identity proof (PDF format strictly enforced)</label>
                  <label className="file-input">
                    <FileImage size={18} />
                    <span>{registrationFileName || 'Upload PAN/Aadhaar PDF'}</span>
                    <input name="id_card" type="file" accept="application/pdf" required onChange={(e) => setRegistrationFileName(e.target.files[0]?.name || '')} />
                  </label>
                </div>
              </>
            )}
            
            <div className="input-group">
              <label>Password</label>
              <input 
                name="password" 
                type="password" 
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••" 
                required 
              />
            </div>
            
            <button type="submit" disabled={isAuthSubmitting}>
              {isAuthSubmitting 
                ? (isLoginMode ? 'Establishing Session...' : 'Verifying Identity PDF (please wait)...') 
                : (isLoginMode ? `Login as ${loginRoleTab.toUpperCase()}` : 'Register Customer Profile')
              }
            </button>
            
            {isLoginMode && (
              <p style={{marginTop: '0.8rem', textAlign: 'center', fontSize: '12px'}}>
                <a href="#" onClick={(e) => { e.preventDefault(); setIsForgotPasswordMode(true); }} style={{ color: 'var(--mono-text-light)' }}>
                  🔑 Forgot Password? Reset Here
                </a>
              </p>
            )}
            
            {loginRoleTab === 'customer' && (
              <p style={{marginTop: '0.6rem', textAlign: 'center', fontSize: '13px'}}>
                <a href="#" onClick={(e) => { e.preventDefault(); setIsLoginMode(!isLoginMode); setAuthError(''); setLoginUsername(''); setLoginPassword(''); }}>
                  {isLoginMode ? 'New Customer? Register Profile' : 'Already registered? Customer Login'}
                </a>
              </p>
            )}
          </form>
        </div>
      </main>
    );
  }

  const analytics = {
    total: claims.length,
    approved: claims.filter(c => c.status === 'APPROVED').length,
    underReview: claims.filter(c => c.status === 'UNDER_REVIEW').length,
    processing: claims.filter(c => c.status === 'PROCESSING' || c.status === 'SUBMITTED').length,
    avgRiskScore: claims.length ? Math.round(claims.reduce((acc, c) => acc + (c.risk_score || 0), 0) / claims.length) : 0
  };

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={28} style={{ color: 'var(--mono-primary)' }} />
            <h1 style={{ fontSize: '24px' }}>Claims Guard terminal</h1>
          </div>
          <span className="eyebrow" style={{ color: 'var(--mono-text)' }}>ROLE: {user.role.toUpperCase()}</span>
        </div>
        <div style={{display: 'flex', gap: '1rem', alignItems: 'center'}}>
          <div className="status-pill" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 12px' }}>
            <span style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <UserIcon size={12} /> {user.full_name}
            </span>
            <small style={{ fontSize: '10px', opacity: 0.8, fontFamily: 'var(--font-mono)' }}>ID: {user.customer_id}</small>
          </div>
          <button className="icon-btn-logout" onClick={logout} title="Logout" style={{background: 'var(--mono-surface-dark)', border: '2px solid var(--mono-text-dark)', color: 'var(--mono-text-dark)', padding: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center'}}>
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}


      {/* CUSTOMER PORTAL */}
      {user.role === 'customer' && (
        <section className="portal-layout">
          <aside className="portal-sidebar panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--mono-text)', paddingBottom: '8px' }}>
              <h2 style={{ margin: 0, border: 'none', padding: 0 }}>My Claims</h2>
              <button 
                onClick={() => setShowFileClaim(!showFileClaim)}
                style={{ 
                  background: 'var(--mono-primary)', 
                  border: '2px solid var(--mono-text-dark)', 
                  padding: '4px 8px', 
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Plus size={12} /> File New
              </button>
            </div>
            
            <div className="claims-list-scroll">
              {claims.length === 0 && <p className="muted" style={{ fontSize: '13px' }}>No claims filed yet.</p>}
              {claims.map((c) => (
                <div 
                  key={c.id} 
                  className={`queue-card ${selectedId === c.id && !showFileClaim ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedId(c.id);
                    setShowFileClaim(false);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '13px' }}>
                    <span>{c.claim_type.split(' - ')[1] || c.claim_type}</span>
                    <span style={{ 
                      color: c.status === 'APPROVED' ? 'var(--mono-success)' :
                             c.status === 'REJECTED' ? 'var(--mono-danger)' : 'var(--mono-warning)'
                    }}>{c.status}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '4px', opacity: 0.8 }}>
                    <span>₹{c.amount_requested.toLocaleString()}</span>
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </aside>

          <div className="portal-main">
            {showFileClaim ? (
              <form className="panel claim-form" onSubmit={submitClaim} style={{ gridArea: 'auto' }}>
                <h2><UploadCloud size={20} /> File New Insurance Claim</h2>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="input-group">
                    <label>Claimant Full Name</label>
                    <input name="claimant_name" defaultValue={user.full_name} required />
                  </div>
                  <div className="input-group">
                    <label>Policy Number</label>
                    <input name="policy_number" placeholder="POL-8902A" required />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="input-group">
                    <label>Incident Date</label>
                    <input name="incident_date" type="date" required />
                  </div>
                  <div className="input-group">
                    <label>Incident Location (City)</label>
                    <input name="incident_location" placeholder="Mumbai" required />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="input-group">
                    <label>Claim Type Category</label>
                    <select name="claim_type" required defaultValue="Auto - Collision & Accident">
                      <optgroup label="Auto Insurance">
                        <option>Auto - Collision & Accident</option>
                        <option>Auto - Comprehensive (Non-Collision)</option>
                        <option>Auto - Injury & Medical</option>
                        <option>Auto - Vehicle Damage & Services</option>
                      </optgroup>
                      <optgroup label="Health Insurance">
                        <option>Health - Hospitalization</option>
                        <option>Health - Medical Treatment</option>
                        <option>Health - Critical Illness</option>
                        <option>Health - Wellness & Other Benefits</option>
                      </optgroup>
                      <optgroup label="Property Insurance">
                        <option>Property - Building Damage</option>
                        <option>Property - Contents & Personal Property</option>
                        <option>Property - Theft & Vandalism</option>
                        <option>Property - Repair & Restoration</option>
                      </optgroup>
                      <optgroup label="Commercial Insurance">
                        <option>Commercial - Property & Assets</option>
                        <option>Commercial - Liability</option>
                        <option>Commercial - Business Interruption</option>
                        <option>Commercial - Commercial Vehicle & Equipment</option>
                      </optgroup>
                      <optgroup label="Life Insurance">
                        <option>Life - Death Claim</option>
                        <option>Life - Disability</option>
                        <option>Life - Critical Illness</option>
                        <option>Life - Policy Benefits</option>
                      </optgroup>
                    </select>
                  </div>
                  <div className="input-group">
                    <label>Requested Amount (INR ₹)</label>
                    <input 
                      name="amount_requested" 
                      placeholder="Max ₹100,000" 
                      type="number" 
                      min="1" 
                      max="100000" 
                      step="0.01" 
                      required 
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label>Incident Description & Details</label>
                  <textarea name="description" placeholder="Explain the incident, what happened, and details of the damage..." required />
                </div>

                <div className="input-group">
                  <label>Evidence Files (Images, Audio, Video, PDF, Text up to 10MB)</label>
                  <label className="file-input">
                    <FileImage size={18} />
                    <span>{claimFileNames.length > 0 ? `${claimFileNames.length} files selected` : 'Select files to upload'}</span>
                    <input name="files" type="file" accept="image/*,audio/*,video/*,application/pdf,text/plain" multiple required onChange={(e) => setClaimFileNames(Array.from(e.target.files).map(f => f.name))} />
                  </label>
                  {claimFileNames.length > 0 && (
                    <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {claimFileNames.map((name, i) => (
                        <div key={i} style={{ fontSize: '11px', background: 'var(--mono-surface-dark)', padding: '4px 8px', borderRadius: '4px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', color: 'var(--mono-text)' }}>
                          📄 {name}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <button type="submit" disabled={isSubmitting}>
                  <Play size={18} /> {isSubmitting ? 'Uploading Evidence...' : 'Submit Claim to Agent'}
                </button>
              </form>
            ) : selected ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="panel" style={{ background: 'var(--mono-surface-light)', padding: '12px' }}>
                  <h3 style={{ fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px', color: 'var(--mono-text)' }}>Claim Lifecycle Status</h3>
                  <div className="status-tracker">
                    {[
                      { label: 'SUBMITTED', active: ['SUBMITTED', 'PROCESSING', 'AI_COMPLETED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'].includes(selected.status) },
                      { label: 'PROCESSING', active: ['PROCESSING', 'AI_COMPLETED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'].includes(selected.status) },
                      { label: 'AI_COMPLETED', active: ['AI_COMPLETED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'].includes(selected.status) },
                      { label: 'UNDER_REVIEW', active: ['UNDER_REVIEW', 'APPROVED', 'REJECTED'].includes(selected.status) },
                      { label: selected.status === 'REJECTED' ? 'REJECTED' : 'APPROVED', active: ['APPROVED', 'REJECTED'].includes(selected.status), final: true }
                    ].map((step, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ 
                          padding: '4px 8px', 
                          fontSize: '11px', 
                          fontWeight: 'bold',
                          background: step.active ? (step.final && selected.status === 'REJECTED' ? 'var(--mono-danger)' : 'var(--mono-primary)') : 'var(--mono-surface-dark)',
                          color: step.active ? 'var(--mono-text-dark)' : 'var(--mono-text)',
                          border: '1px solid var(--mono-text-dark)'
                        }}>
                          {step.label}
                        </div>
                        {idx < 4 && <ArrowRight size={12} style={{ color: 'var(--mono-text)' }} />}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid" style={{ gridTemplateColumns: '1fr 340px', gridTemplateAreas: '"detail log"' }}>
                  <section className="panel detail" style={{ gridArea: 'detail', overflowY: 'auto' }}>
                    <h2><FileText size={18} /> Claim File: {selected.id.slice(0, 8)}...</h2>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <div className="decision" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                        <div>
                          <span>Status Decision</span>
                          <strong style={{ 
                            color: selected.status === 'APPROVED' ? 'var(--mono-success)' : 
                                   selected.status === 'REJECTED' ? 'var(--mono-danger)' : 'inherit'
                          }}>
                            {selected.decision || selected.status}
                          </strong>
                        </div>
                        <div>
                          <span>Trust Score</span>
                          <strong style={{ color: (selected.risk_score || 50) >= 70 ? 'var(--mono-success)' : (selected.risk_score || 50) >= 50 ? 'var(--mono-warning)' : 'var(--mono-danger)' }}>
                            {selected.risk_score ?? 50}/100
                          </strong>
                        </div>
                        <div>
                          <span>Fraud Risk Level</span>
                          <strong style={{ color: (selected.risk_score || 50) >= 70 ? 'var(--mono-success)' : (selected.risk_score || 50) >= 50 ? 'var(--mono-warning)' : 'var(--mono-danger)' }}>
                            {100 - (selected.risk_score ?? 50)}%
                          </strong>
                        </div>
                      </div>

                      {/* Multi-Sentence Decision Explanation Banner */}
                      {(selected.decision_reason || selected.verification_metadata?.decision_reason) && (
                        <div style={{ background: '#f8fafc', borderLeft: '4px solid #3b82f6', padding: '12px 16px', borderRadius: '4px', marginTop: '10px' }}>
                          <span className="eyebrow" style={{ color: '#1e3a8a', display: 'block', marginBottom: '4px' }}>🔍 Decision Engine Explanation</span>
                          <p style={{ margin: 0, fontSize: '12px', lineHeight: '1.5', color: '#334155', fontWeight: '500' }}>
                            {selected.decision_reason || selected.verification_metadata?.decision_reason}
                          </p>
                        </div>
                      )}

                      {/* Recommended Next Actions */}
                      {selected.verification_metadata?.next_actions && selected.verification_metadata.next_actions.length > 0 && (
                        <div style={{ background: '#faf5ff', border: '1px solid #e9d5ff', padding: '12px 16px', borderRadius: '4px', marginTop: '10px' }}>
                          <span className="eyebrow" style={{ color: '#6b21a8', display: 'block', marginBottom: '4px' }}>📋 Recommended Next Actions</span>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {selected.verification_metadata.next_actions.map((act, idx) => {
                              const displayAct = (user?.role === 'customer' || !user || user.role !== 'adjuster') && 
                                (act.includes('Notify') || act.includes('Policyholder'))
                                ? "Check Settlement Transfer Status"
                                : act;
                              return (
                                <div key={idx} style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#581c87', fontWeight: '500' }}>
                                  <span style={{ color: '#9333ea', fontWeight: 'bold' }}>✓</span> {displayAct}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <div style={{ border: '1px solid var(--mono-surface-dark)', padding: '12px', background: 'var(--mono-surface)' }}>
                        <span className="eyebrow">Claim Details & Statement</span>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px', marginTop: '6px' }}>
                          <div><strong>Claimant:</strong> {selected.claimant_name}</div>
                          <div><strong>Policy #:</strong> {selected.policy_number}</div>
                          <div><strong>Location:</strong> {selected.incident_location}</div>
                          <div><strong>Date:</strong> {selected.incident_date ? new Date(selected.incident_date).toLocaleDateString() : '-'}</div>
                        </div>
                        {selected.description && (
                          <div style={{ background: '#fff', border: '1px solid #cbd5e1', padding: '10px 12px', borderRadius: '6px', marginTop: '10px' }}>
                            <strong style={{ fontSize: '12px', color: '#334155', display: 'block', marginBottom: '4px' }}>📝 Policyholder Statement / Description:</strong>
                            <p style={{ margin: 0, fontSize: '12px', color: '#1e293b', lineHeight: '1.5' }}>{selected.description}</p>
                          </div>
                        )}
                      </div>

                      {selected.investigation_summary && (
                        <div>
                          <span className="eyebrow" style={{ color: 'var(--mono-text)' }}>AI Investigation Summary</span>
                          <p style={{ marginTop: '4px', fontSize: '13px', lineHeight: '1.4' }}>{selected.investigation_summary}</p>
                        </div>
                      )}

                      {selected.shap_explanations && selected.shap_explanations.length > 0 && (
                        <div style={{ border: '2px solid var(--mono-secondary)', padding: '12px', background: 'rgba(0, 166, 244, 0.04)', borderLeft: '4px solid var(--mono-secondary)' }}>
                          <span className="eyebrow" style={{ color: 'var(--mono-secondary)' }}>AI Risk Factors Explained</span>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                            {selected.shap_explanations.map((featObj, idx) => {
                              const feat = typeof featObj === 'string' ? featObj : featObj.feature;
                              const impact = typeof featObj === 'string' ? null : featObj.impact;
                              const explanations = {
                                "claim_amount": "Claim Payout Amount: Evaluates if the requested payout is unusually high for this category.",
                                "previous_claims": "Claim History: Looks at the frequency of past claims filed by this user.",
                                "policy_age": "Policy Age: Checks if the insurance policy was purchased right before the incident.",
                                "customer_tenure": "Account Age: Considers how long the user has been a customer.",
                                "claim_submission_delay": "Submission Delay: Measures the time lag between the incident and the claim filing.",
                                "weather_verified": "Weather Verification: Cross-checks local weather reports against the claim details.",
                                "location_verified": "Location Verification: Validates geolocation data matches the incident report.",
                                "disaster_verified": "Disaster Alerts: Checks for natural disaster warnings in the region during the incident.",
                                "image_anomaly_score": "Evidence Authenticity: Scans uploaded photos for digital manipulation or metadata inconsistencies.",
                                "document_consistency_score": "Document Consistency: Analyzes text and visual consistency across all uploaded paperwork.",
                                "missing_document_count": "Documentation Completeness: Checks if required proof or verification statements are missing.",
                                "ocr_consistency_score": "Text Consistency: Cross-checks text found in images against the claim details."
                              };
                              
                              const directionText = impact === null ? "Evaluated" : (impact > 0 ? "Increased Risk" : "Decreased Risk");
                              const directionColor = impact === null ? "var(--mono-text)" : (impact > 0 ? "var(--mono-danger)" : "var(--mono-success)");
                              const desc = explanations[feat] || "Structured features contributed to the overall risk evaluation.";

                              return (
                                <div key={idx} style={{ fontSize: '12px', color: 'var(--mono-text-dark)', padding: '6px 0', borderBottom: idx !== selected.shap_explanations.length - 1 ? '1px solid var(--mono-surface)' : 'none' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                                    <strong>{desc.split(':')[0]}</strong>
                                    <span style={{ color: directionColor, fontWeight: 'bold' }}>{directionText}</span>
                                  </div>
                                  <div style={{ color: 'var(--mono-text)' }}>{desc.split(':')[1] || desc}</div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {user && (user.role === 'adjuster' || user.role === 'admin') && (() => {
                        const renderCheck = (label, key) => {
                          const status = selected[`${key}_verification_status`] || 'NOT_REQUIRED';
                          const meta = (selected.verification_metadata && 
                                        (selected.verification_metadata.verifications?.[key] || selected.verification_metadata[key])) || {};
                          const reason = meta.reason || '';
                          const source = meta.source || '';
                          const timestamp = meta.timestamp ? new Date(meta.timestamp).toLocaleTimeString() : '';

                          const statusIcons = {
                            'PASSED': '☑',
                            'FAILED': '☒',
                            'NOT_REQUIRED': '🛈',
                            'UNKNOWN': '⚠'
                          };
                          
                          const statusColors = {
                            'PASSED': 'var(--mono-success)',
                            'FAILED': 'var(--mono-danger)',
                            'NOT_REQUIRED': 'var(--mono-text-light)',
                            'UNKNOWN': 'var(--mono-warning, #f59e0b)'
                          };
                          
                          const color = statusColors[status] || 'inherit';
                          const icon = statusIcons[status] || '☐';
                          
                          return (
                            <div key={key} style={{ paddingBottom: '8px', borderBottom: '1px solid var(--mono-surface-dark)' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                                <strong>{label}</strong>
                                <span style={{ color: color, fontWeight: 'bold' }}>{icon} {status}</span>
                              </div>
                              {reason && <div style={{ fontSize: '11px', color: 'var(--mono-text)', marginTop: '2px', lineHeight: '1.3' }}>{reason}</div>}
                              {source && (
                                <div style={{ fontSize: '10px', color: 'var(--mono-text-light)', marginTop: '2px', display: 'flex', justifyContent: 'space-between' }}>
                                  <span>Source: {source}</span>
                                  {timestamp && <span>{timestamp}</span>}
                                </div>
                              )}
                            </div>
                          );
                        };

                        return (
                          <div style={{ border: '2px solid var(--mono-text-dark)', padding: '12px', background: 'var(--mono-surface-light)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            <span className="eyebrow" style={{ color: 'var(--mono-text-dark)' }}>Verification Checklist</span>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                              {renderCheck('Location Verification', 'location')}
                              {renderCheck('Weather Verification', 'weather')}
                              {renderCheck('Disaster Verification', 'disaster')}
                              {renderCheck('Event Verification', 'event')}
                            </div>
                            
                            <div style={{ fontSize: '11px', color: 'var(--mono-text-light)', display: 'flex', justifyContent: 'space-between', marginTop: '6px', paddingTop: '6px', borderTop: '1px dashed var(--mono-surface-dark)' }}>
                              <span>Pipeline: {selected.investigation_version || 'v1.0'}</span>
                              {selected.processing_duration_ms !== null && <span>Latency: {(selected.processing_duration_ms / 1000).toFixed(2)}s</span>}
                            </div>
                            
                            {selected.fallback_reason && (
                              <div style={{ background: 'rgba(239, 68, 68, 0.06)', borderLeft: '3px solid var(--mono-danger)', padding: '6px', fontSize: '11px', color: 'var(--mono-danger)', marginTop: '4px', lineHeight: '1.3' }}>
                                <strong>AI Fallback:</strong> {selected.fallback_reason}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {selected.adjuster_notes && (
                        <div style={{ border: '2px solid var(--mono-text-dark)', padding: '12px', background: '#fff' }}>
                          <span className="eyebrow" style={{ color: 'var(--mono-text-dark)' }}>Claims Adjuster Notes</span>
                          <p style={{ marginTop: '4px', fontSize: '13px', fontWeight: 'bold' }}>{selected.adjuster_notes}</p>
                        </div>
                      )}

                      {selected.reviewed_by_id && (
                        <div style={{ border: '2px solid var(--mono-text-dark)', padding: '12px', background: '#fff', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <span className="eyebrow" style={{ color: 'var(--mono-text-dark)' }}>Adjuster Override Trail</span>
                          <div style={{ fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <div><strong>Reviewed By:</strong> {selected.reviewed_by_user?.full_name || 'System Adjuster'} (ID: {selected.reviewed_by_id})</div>
                            <div><strong>Reviewed At:</strong> {selected.reviewed_at ? new Date(selected.reviewed_at).toLocaleString() : '-'}</div>
                            {selected.reviewer_notes && (
                              <div style={{ marginTop: '4px', background: 'var(--mono-surface)', padding: '6px', borderLeft: '3px solid var(--mono-text-dark)', fontStyle: 'italic' }}>
                                "{selected.reviewer_notes}"
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      <div>
                        <span className="eyebrow" style={{ color: 'var(--mono-text)' }}>Evidence Gallery</span>
                        <div className="evidence" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                          {selected.evidence.map((item) => (
                            <div key={item.id} style={{ border: '1px solid var(--mono-text-dark)', padding: '4px', background: 'var(--mono-surface)' }}>
                              <a href={item.url} target="_blank" rel="noreferrer" style={{ fontSize: '11px', display: 'block', maxWidth: '120px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                {item.filename}
                              </a>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>

                  <section className="panel agent-log" style={{ gridArea: 'log' }}>
                    <h2>Live Investigation Logs</h2>
                    {events.length === 0 && <p className="muted" style={{ fontSize: '12px' }}>Awaiting terminal stream...</p>}
                    {events.map((event) => (
                      <article key={event.id} className={`event ${event.status}`}>
                        <span>{event.step}</span>
                        <p style={{ fontSize: '12px' }}>{event.message}</p>
                      </article>
                    ))}
                  </section>
                </div>
              </div>
            ) : (
              <div className="panel" style={{ padding: '3rem', textAlign: 'center' }}>
                <FileText size={48} style={{ color: 'var(--mono-text)', margin: '0 auto 1rem', display: 'block' }} />
                <h3>Select a claim from the sidebar or submit a new one to view details.</h3>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ADJUSTER DASHBOARD */}
      {user.role === 'adjuster' && (
        <section className="portal-layout">
          <aside className="portal-sidebar panel">
            <h2 style={{ borderBottom: '1px solid var(--mono-text)', paddingBottom: '8px' }}>Assigned Queue</h2>
            <div className="claims-list-scroll">
              {claims.length === 0 && <p className="muted">No claims currently assigned to you.</p>}
              {claims.map((c) => {
                const trustScore = c.risk_score ?? 50;
                const riskLabel = trustScore >= 70 ? 'LOW RISK' : trustScore >= 40 ? 'MED RISK' : 'HIGH RISK';
                const riskColor = trustScore >= 70 ? 'var(--mono-success)' : trustScore >= 40 ? 'var(--mono-warning)' : 'var(--mono-danger)';
                return (
                  <div 
                    key={c.id} 
                    className={`queue-card ${selectedId === c.id ? 'active' : ''}`}
                    onClick={() => setSelectedId(c.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '13px' }}>
                      <span>{c.claimant_name}</span>
                      <span style={{ 
                        color: riskColor,
                        fontSize: '11px',
                        background: 'rgba(0,0,0,0.05)',
                        padding: '1px 4px'
                      }}>
                        {riskLabel}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '4px', opacity: 0.8 }}>
                      <span>Score: {c.risk_score ?? '-'}</span>
                      <span>⚖️ {c.assigned_adjuster?.full_name || 'Unassigned'}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </aside>

          <div className="portal-main">
            {selected ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="panel">
                    <h2>Claim Assessment: {selected.id.slice(0, 8)}...</h2>
                    
                    <div className="decision" style={{ gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                      <div>
                        <span>Claimant</span>
                        <strong>{selected.claimant_name}</strong>
                      </div>
                      <div>
                        <span>Requested</span>
                        <strong>₹{selected.amount_requested.toLocaleString()}</strong>
                      </div>
                      <div>
                        <span>Trust Score</span>
                        <strong style={{ color: selected.status === 'PROCESSING' || selected.status === 'SUBMITTED' ? 'var(--mono-warning)' : (selected.risk_score || 50) >= 70 ? 'var(--mono-success)' : (selected.risk_score || 50) >= 50 ? 'var(--mono-warning)' : 'var(--mono-danger)' }}>
                          {selected.status === 'PROCESSING' || selected.status === 'SUBMITTED' || selected.risk_score === null ? '⏳ Evaluating...' : `${selected.risk_score}/100`}
                        </strong>
                        <small style={{ fontSize: '9px', display: 'block', color: 'var(--mono-text-dark)', marginTop: '2px' }}>
                          Fraud Risk: {selected.status === 'PROCESSING' || selected.status === 'SUBMITTED' || selected.risk_score === null ? 'Calculating...' : `${100 - selected.risk_score}%`}
                        </small>
                      </div>
                      <div>
                        <span>Evidence Confidence</span>
                        <strong style={{ color: 'var(--mono-primary)' }}>
                          {selected.status === 'PROCESSING' || selected.status === 'SUBMITTED' ? '⏳ Calculating...' : `${selected.verification_metadata?.evidence_confidence ?? 95}%`}
                        </strong>
                      </div>
                      <div>
                        <span>Workflow Status</span>
                        <strong style={{ 
                          fontSize: '11px', 
                          padding: '3px 8px', 
                          borderRadius: '4px',
                          display: 'inline-block',
                          marginTop: '4px',
                          textTransform: 'uppercase',
                          background: selected.status === 'APPROVED' ? '#dcfce7' : selected.status === 'REJECTED' ? '#fee2e2' : selected.status === 'PROCESSING' ? '#e0e7ff' : '#fef3c7',
                          color: selected.status === 'APPROVED' ? '#166534' : selected.status === 'REJECTED' ? '#991b1b' : selected.status === 'PROCESSING' ? '#3730a3' : '#92400e'
                        }}>
                          {selected.status}
                        </strong>
                      </div>
                    </div>

                    <div style={{ marginTop: '12px', fontSize: '13px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div><strong>Policy #:</strong> {selected.policy_number}</div>
                      <div><strong>Incident Date:</strong> {selected.incident_date ? new Date(selected.incident_date).toLocaleDateString() : '-'}</div>
                      <div><strong>Incident Location:</strong> {selected.incident_location}</div>
                    </div>

                    {selected.description && (
                      <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', padding: '10px 12px', borderRadius: '6px', marginTop: '10px' }}>
                        <strong style={{ fontSize: '12px', color: '#334155', display: 'block', marginBottom: '4px' }}>📝 Policyholder Statement / Description:</strong>
                        <p style={{ margin: 0, fontSize: '12px', color: '#1e293b', lineHeight: '1.5' }}>{selected.description}</p>
                      </div>
                    )}
                  </div>

                  {/* Multi-Sentence Decision Explanation Banner */}
                  {(selected.decision_reason || selected.verification_metadata?.decision_reason) && (
                    <div className="panel" style={{ background: '#f8fafc', borderLeft: '4px solid #3b82f6', padding: '12px 16px' }}>
                      <h3 style={{ margin: '0 0 6px 0', color: '#1e3a8a', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        🔍 Decision Engine Explanation
                      </h3>
                      <p style={{ margin: 0, fontSize: '12px', lineHeight: '1.5', color: '#334155', fontWeight: '500' }}>
                        {selected.decision_reason || selected.verification_metadata?.decision_reason}
                      </p>
                    </div>
                  )}

                  {/* Actionable Next Actions Checklist Card (Dynamic based on Status) */}
                  {(() => {
                    let nextActions = selected.verification_metadata?.next_actions;
                    if (selected.status === 'APPROVED') {
                      nextActions = [
                        "Disburse claim payout to policyholder account",
                        "Dispatch formal approval email notice",
                        "Archive claim file in audit repository"
                      ];
                    } else if (selected.status === 'REJECTED') {
                      nextActions = [
                        "Issue formal denial letter explaining policy grounds",
                        "Log rejection rationale in compliance database",
                        "Close active claim file"
                      ];
                    } else if (selected.status === 'UNDER_REVIEW') {
                      nextActions = [
                        "Request supplemental documentation / receipts from policyholder",
                        "Schedule secondary adjuster review upon receipt of documents"
                      ];
                    }

                    return nextActions && nextActions.length > 0 ? (
                      <div className="panel" style={{ background: '#faf5ff', border: '1px solid #e9d5ff' }}>
                        <h3 style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#6b21a8' }}>📋 Recommended Next Actions</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {nextActions.map((act, idx) => (
                            <div key={idx} style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#581c87', fontWeight: '500' }}>
                              <span style={{ color: '#9333ea', fontWeight: 'bold' }}>✓</span> {act}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null;
                  })()}

                  {/* Top Positive & Top Negative Rules Cards */}
                  {selected.verification_metadata?.top_positive && (
                    <div className="panel" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '10px', borderRadius: '6px' }}>
                        <strong style={{ fontSize: '12px', color: '#166534', display: 'block', marginBottom: '6px' }}>🟢 Top Positive Factors</strong>
                        {selected.verification_metadata.top_positive.length > 0 ? (
                          selected.verification_metadata.top_positive.map((item, idx) => (
                            <div key={idx} style={{ fontSize: '11px', color: '#15803d', marginBottom: '3px', fontWeight: '500' }}>{item}</div>
                          ))
                        ) : <div style={{ fontSize: '11px', color: '#666' }}>None triggered</div>}
                      </div>
                      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '10px', borderRadius: '6px' }}>
                        <strong style={{ fontSize: '12px', color: '#991b1b', display: 'block', marginBottom: '6px' }}>🔴 Top Risk Factors</strong>
                        {selected.verification_metadata.top_negative.length > 0 ? (
                          selected.verification_metadata.top_negative.map((item, idx) => (
                            <div key={idx} style={{ fontSize: '11px', color: '#b91c1c', marginBottom: '3px', fontWeight: '500' }}>{item}</div>
                          ))
                        ) : <div style={{ fontSize: '11px', color: '#666' }}>None triggered</div>}
                      </div>
                    </div>
                  )}

                  {/* Verification Checks Summary */}
                  {selected.verification_metadata?.verification_status && (
                    <div className="panel">
                      <h3>✅ Automated Verification Checks</h3>
                      <p style={{ fontSize: '11px', color: '#64748b', marginBottom: '10px' }}>Summary of automated background checks executed for this claim.</p>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px' }}>
                        {Object.entries(selected.verification_metadata.verification_status).map(([src, obj]) => {
                          const status = obj.status || "SKIPPED";
                          const isOk = status === "SUCCESS";
                          const isFail = status === "FAILED";
                          const friendlyNames = {
                            identity: '🪪 Identity Check',
                            policy: '📋 Policy Check',
                            location: '📍 Location Verification',
                            weather: '🌦️ Weather Records',
                            news: '📰 News Verification',
                            gdacs: '🌍 Disaster Records',
                            gemini_vision: '🔍 Photo Inspection',
                            ocr: '📄 Document Scan',
                            osm: '🗺️ Map Verification'
                          };
                          const friendlyStatus = isOk ? 'Verified ✅' : isFail ? 'Failed ❌' : 'Not Needed ⏭️';
                          return (
                            <div key={src} style={{
                              padding: '10px 12px',
                              borderRadius: '8px',
                              background: isOk ? '#f0fdf4' : isFail ? '#fef2f2' : '#f9fafb',
                              border: `1px solid ${isOk ? '#bbf7d0' : isFail ? '#fecaca' : '#e5e7eb'}`,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px'
                            }}>
                              <div style={{ fontSize: '12px', fontWeight: '600', color: '#1e293b' }}>
                                <div>{friendlyNames[src] || src.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                                <div style={{ fontSize: '10px', color: isOk ? '#16a34a' : isFail ? '#dc2626' : '#6b7280', fontWeight: '500', marginTop: '2px' }}>
                                  {friendlyStatus}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Triggered Rules Audit Table (Strictly Synchronized with Automated Checks Status) */}
                  {selected.verification_metadata?.triggered_rules && (() => {
                    const vStatus = selected.verification_metadata.verification_status || {};
                    const validRules = selected.verification_metadata.triggered_rules.filter(rule => {
                      if (rule.category === 'Identity' && vStatus.identity?.status !== 'SUCCESS') return false;
                      if (rule.category === 'Weather' && vStatus.weather?.status !== 'SUCCESS') return false;
                      if (rule.category === 'News' && vStatus.news?.status !== 'SUCCESS') return false;
                      if (rule.category === 'Location' && vStatus.location?.status !== 'SUCCESS') return false;
                      return true;
                    });

                    return (
                      <div className="panel">
                        <h3>📊 Risk Scoring Factors</h3>
                        <p style={{ fontSize: '11px', color: '#64748b', marginBottom: '10px' }}>Key factors that influenced the trust score evaluation.</p>
                        <div style={{ marginTop: '8px', overflowX: 'auto' }}>
                          <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                                <th style={{ padding: '6px' }}>Category</th>
                                <th style={{ padding: '6px' }}>Verification Factor</th>
                                <th style={{ padding: '6px' }}>Score Impact</th>
                                <th style={{ padding: '6px' }}>Details</th>
                              </tr>
                            </thead>
                            <tbody>
                              {validRules.map((rule, idx) => {
                                const isPos = rule.score > 0;
                                return (
                                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                    <td style={{ padding: '6px', fontWeight: 'bold' }}>{rule.category}</td>
                                    <td style={{ padding: '6px' }}>{rule.rule}</td>
                                    <td style={{ padding: '6px', fontWeight: 'bold', color: isPos ? '#16a34a' : '#dc2626' }}>
                                      {isPos ? `+${rule.score}` : rule.score}
                                    </td>
                                    <td style={{ padding: '6px', color: '#475569' }}>{rule.description}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}

                  {/* AI Evidence Summary */}
                  {selected.verification_metadata?.evidence && (() => {
                    const ev = selected.verification_metadata.evidence;
                    const cards = [];

                    if (ev.gemini) {
                      const items = [
                        ev.gemini.damage_summary && { label: 'Observation', value: ev.gemini.damage_summary },
                        ev.gemini.consistency && { label: 'Consistency', value: ev.gemini.consistency },
                        ev.gemini.red_flags && { label: 'Red Flags', value: ev.gemini.red_flags },
                        ev.gemini.confidence && { label: 'Confidence', value: ev.gemini.confidence }
                      ].filter(Boolean);
                      if (items.length > 0) cards.push({ icon: '🔍', title: 'AI Photo Inspection', items });
                    }
                    if (ev.weather) {
                      const items = [
                        ev.weather.rain_mm != null && { label: 'Rainfall', value: `${ev.weather.rain_mm} mm` },
                        ev.weather.wind_kmh != null && { label: 'Wind Speed', value: `${ev.weather.wind_kmh} km/h` },
                        ev.weather.weather_verified != null && { label: 'Matches Report', value: ev.weather.weather_verified ? 'Yes ✅' : 'No ❌' }
                      ].filter(Boolean);
                      if (items.length > 0) cards.push({ icon: '🌦️', title: 'Local Weather Data', items });
                    }
                    if (ev.policy) {
                      const items = [
                        ev.policy.policy_type && { label: 'Policy Type', value: ev.policy.policy_type },
                        ev.policy.coverage_limit && { label: 'Limit', value: `₹${Number(ev.policy.coverage_limit).toLocaleString()}` },
                        ev.policy.status && { label: 'Policy Status', value: ev.policy.status }
                      ].filter(Boolean);
                      if (items.length > 0) cards.push({ icon: '📋', title: 'Policy Verification', items });
                    }
                    if (ev.osm) {
                      const items = [
                        ev.osm.display_name && { label: 'Address', value: ev.osm.display_name },
                        ev.osm.type && { label: 'Zone Type', value: ev.osm.type }
                      ].filter(Boolean);
                      if (items.length > 0) cards.push({ icon: '🗺️', title: 'Location Mapping', items });
                    }

                    return cards.length > 0 ? (
                      <div className="panel">
                        <h3>📋 Verification Evidence Summary</h3>
                        <p style={{ fontSize: '11px', color: '#64748b', marginBottom: '10px' }}>Visual breakdown of evidence gathered for this claim.</p>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                          {cards.map((card, i) => (
                            <div key={i} style={{
                              padding: '12px 14px',
                              borderRadius: '8px',
                              background: '#f8fafc',
                              border: '1px solid #e2e8f0'
                            }}>
                              <div style={{ fontSize: '13px', fontWeight: '700', color: '#0f172a', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontSize: '16px' }}>{card.icon}</span> {card.title}
                              </div>
                              {card.items.map((item, j) => (
                                <div key={j} style={{ fontSize: '11px', marginBottom: '4px', display: 'flex', gap: '6px' }}>
                                  <span style={{ color: '#64748b', minWidth: '85px', fontWeight: '600' }}>{item.label}:</span>
                                  <span style={{ color: '#1e293b', flex: 1 }}>{item.value}</span>
                                </div>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null;
                  })()}

                  <div className="panel">
                    <h3>AI Investigation Summary</h3>
                    <p style={{ fontSize: '13px', lineHeight: '1.4' }}>{selected.investigation_summary || selected.summary}</p>
                  </div>

                  <div className="panel">
                    <h3>Uploaded Evidence Files</h3>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                      {selected.evidence.map((item) => (
                        <div key={item.id} style={{ border: '2px solid var(--mono-text-dark)', padding: '6px', background: 'var(--mono-surface-light)' }}>
                          <a href={item.url} target="_blank" rel="noreferrer" style={{ fontSize: '12px', display: 'block', fontWeight: 'bold' }}>
                            {item.filename}
                          </a>
                          <small style={{ fontSize: '10px', color: 'var(--mono-text)' }}>{item.content_type}</small>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <form className="panel claim-form" onSubmit={handleAdjudicate} style={{ gridArea: 'auto' }}>
                    <h2>Adjudicate Override</h2>
                    
                    <div className="input-group">
                      <label>Action Override</label>
                      <select 
                        value={adjudicationAction} 
                        onChange={(e) => setAdjudicationAction(e.target.value)}
                      >
                        <option value="APPROVE">APPROVE CLAIM</option>
                        <option value="REJECT">REJECT CLAIM</option>
                        <option value="REQUEST_DOCUMENTS">REQUEST MORE DOCUMENTS</option>
                      </select>
                    </div>

                    <div className="input-group">
                      <label>Internal Adjusted Notes</label>
                      <textarea 
                        placeholder="Log notes detailing why the override was made..."
                        value={adjudicationNotes}
                        onChange={(e) => setAdjudicationNotes(e.target.value)}
                        required
                      />
                    </div>

                    <button type="submit" style={{ background: 'var(--mono-primary)' }}>
                      Submit Override
                    </button>
                  </form>

                  <div className="panel" style={{ background: 'var(--mono-surface)' }}>
                    <h3 style={{ fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Claim History Timeline</h3>
                    <div style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div><strong>Created:</strong> {new Date(selected.created_at).toLocaleString()}</div>
                      {selected.processing_timestamp && (
                        <div><strong>AI Checked:</strong> {new Date(selected.processing_timestamp).toLocaleString()}</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="panel" style={{ padding: '3rem', textAlign: 'center' }}>
                <FileText size={48} style={{ color: 'var(--mono-text)', margin: '0 auto 1rem', display: 'block' }} />
                <h3>Select an assigned claim from the sidebar queue to review.</h3>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ADMIN PANEL */}
      {user.role === 'admin' && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="admin-tabs">
            {[
              { id: 'claims', label: 'Claims Registry', icon: FileText },
              { id: 'users', label: 'User Directory & Roles', icon: Users },
              { id: 'audit', label: 'System Audit Logs', icon: List },
              { id: 'analytics', label: 'Analytics Insights', icon: Activity }
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button 
                  key={tab.id}
                  onClick={() => setCurrentTab(tab.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    background: currentTab === tab.id ? 'var(--mono-primary)' : 'var(--mono-surface-light)',
                    color: 'var(--mono-text-dark)',
                    border: '2px solid var(--mono-text-dark)',
                    fontSize: '13px'
                  }}
                >
                  <Icon size={14} /> {tab.label}
                </button>
              );
            })}
          </div>

          {/* TAB 1: Claims Registry */}
          {currentTab === 'claims' && (
            <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '16px' }}>
              <aside className="panel" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                <h3 style={{ fontSize: '13px', textTransform: 'uppercase', marginBottom: '8px', borderBottom: '1px solid var(--mono-text)', paddingBottom: '4px' }}>All System Claims</h3>
                
                {/* Separate Search Filters */}
                <div style={{ marginBottom: '12px', display: 'flex', flexDirection: 'column', gap: '6px', background: '#f8fafc', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#475569', textTransform: 'uppercase' }}>🔎 Search & Filter Claims</div>
                  <input 
                    type="text"
                    placeholder="Filter by Customer ID (e.g. CUST-10492)"
                    value={filterCustId}
                    onChange={(e) => setFilterCustId(e.target.value)}
                    style={{ padding: '5px 8px', fontSize: '11px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#fff' }}
                  />
                  <input 
                    type="text"
                    placeholder="Filter by Claimant Name"
                    value={filterClaimantName}
                    onChange={(e) => setFilterClaimantName(e.target.value)}
                    style={{ padding: '5px 8px', fontSize: '11px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#fff' }}
                  />
                  <input 
                    type="text"
                    placeholder="Filter by Claim ID or Policy #"
                    value={filterClaimId}
                    onChange={(e) => setFilterClaimId(e.target.value)}
                    style={{ padding: '5px 8px', fontSize: '11px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#fff' }}
                  />
                  <select 
                    value={filterAdjusterId}
                    onChange={(e) => setFilterAdjusterId(e.target.value)}
                    style={{ padding: '5px 8px', fontSize: '11px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#fff' }}
                  >
                    <option value="">-- All Assigned Adjusters --</option>
                    {allUsers.filter(u => u.role === 'adjuster').map(adj => (
                      <option key={adj.id} value={adj.id}>⚖️ {adj.full_name} ({adj.username})</option>
                    ))}
                  </select>
                  {(filterCustId || filterClaimantName || filterClaimId || filterAdjusterId) && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
                      <span style={{ fontSize: '10px', color: '#64748b' }}>Found {filteredAdminClaims.length} matching claim(s)</span>
                      <button 
                        type="button" 
                        onClick={() => { setFilterCustId(''); setFilterClaimantName(''); setFilterClaimId(''); setFilterAdjusterId(''); }}
                        style={{ fontSize: '10px', padding: '2px 6px', background: '#e2e8f0', color: '#334155', border: 'none', borderRadius: '3px', cursor: 'pointer' }}
                      >
                        Clear Filters
                      </button>
                    </div>
                  )}
                </div>

                <div className="claims-list-scroll">
                  {filteredAdminClaims.length === 0 && (
                    <p className="muted" style={{ fontSize: '12px', padding: '8px 0' }}>
                      {(filterCustId || filterClaimantName || filterClaimId || filterAdjusterId) ? 'No claims matching applied filters.' : 'No claims registered.'}
                    </p>
                  )}
                  {filteredAdminClaims.map((c) => (
                    <div 
                      key={c.id} 
                      className={`queue-card ${selectedId === c.id ? 'active' : ''}`}
                      onClick={() => setSelectedId(c.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '13px', alignItems: 'center' }}>
                        <span>{c.claimant_name}</span>
                        <span style={{ 
                          fontSize: '10px',
                          fontWeight: 'bold',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          textTransform: 'uppercase',
                          background: c.status === 'APPROVED' ? '#dcfce7' : c.status === 'REJECTED' ? '#fee2e2' : c.status === 'PROCESSING' ? '#e0e7ff' : '#fef3c7',
                          color: c.status === 'APPROVED' ? '#166534' : c.status === 'REJECTED' ? '#991b1b' : c.status === 'PROCESSING' ? '#3730a3' : '#92400e'
                        }}>
                          {c.status}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', fontSize: '11px', marginTop: '4px', opacity: 0.85 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>ID: {c.id.slice(0, 8)}...</span>
                        <span style={{ fontSize: '10px', color: '#166534', fontWeight: 'bold' }}>
                          ⚖️ {c.assigned_adjuster?.full_name || 'Unassigned'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </aside>

              <div className="portal-main">
                {selected ? (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '16px' }}>
                    <div className="panel">
                      <h2>System Claim File: {selected.id}</h2>
                      
                      <div className="decision" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                        <div>
                          <span>Customer ID</span>
                          <strong>{selected.user?.customer_id || 'N/A'}</strong>
                        </div>
                        <div>
                          <span>Claimant</span>
                          <strong>{selected.claimant_name}</strong>
                        </div>
                        <div>
                          <span>Requested</span>
                          <strong>₹{selected.amount_requested.toLocaleString()}</strong>
                        </div>
                        <div>
                          <span>Workflow Status</span>
                          <strong>{selected.status}</strong>
                        </div>
                      </div>

                      <div style={{ marginTop: '12px', fontSize: '13px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <div><strong>Policy Number:</strong> {selected.policy_number}</div>
                        <div><strong>Incident Location:</strong> {selected.incident_location}</div>
                        <div><strong>Incident Date:</strong> {selected.incident_date ? new Date(selected.incident_date).toLocaleDateString() : '-'}</div>
                        <div><strong>Assigned Adjudicator:</strong> {selected.assigned_adjuster?.full_name ? `${selected.assigned_adjuster.full_name} (${selected.assigned_adjuster.username})` : 'Unassigned'}</div>
                      </div>

                      <div style={{ marginTop: '16px' }}>
                        <span className="eyebrow">AI adjudication Summary</span>
                        <p style={{ fontSize: '13px', marginTop: '4px' }}>{selected.investigation_summary || selected.summary || 'Investigation not run yet.'}</p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <form className="panel claim-form" onSubmit={handleAssign} style={{ gridArea: 'auto' }}>
                        <h2>{selected.assigned_adjuster_id ? 'Reassign Claim to Adjuster' : 'Assign Adjuster'}</h2>
                        <div className="input-group">
                          <label>Select Claims Adjuster</label>
                          <select 
                            value={assigneeId} 
                            onChange={(e) => setAssigneeId(e.target.value)}
                            required
                          >
                            <option value="">-- Choose Adjuster --</option>
                            {allUsers.filter(u => u.role === 'adjuster').map((adj) => (
                              <option key={adj.id} value={adj.id}>{adj.full_name} ({adj.username})</option>
                            ))}
                          </select>
                        </div>
                        <button type="submit" style={{ background: 'var(--mono-secondary)', color: '#fff' }}>
                          {selected.assigned_adjuster_id ? 'Reassign Claim' : 'Assign Claim'}
                        </button>
                      </form>

                      <form className="panel claim-form" onSubmit={handleAdjudicate} style={{ gridArea: 'auto' }}>
                        <h2>Admin Override</h2>
                        <div className="input-group">
                          <label>Adjudication override</label>
                          <select 
                            value={adjudicationAction} 
                            onChange={(e) => setAdjudicationAction(e.target.value)}
                          >
                            <option value="APPROVE">APPROVE CLAIM</option>
                            <option value="REJECT">REJECT CLAIM</option>
                          </select>
                        </div>
                        <div className="input-group">
                          <label>Override Justification</label>
                          <textarea 
                            placeholder="Reason for admin decision override..."
                            value={adjudicationNotes}
                            onChange={(e) => setAdjudicationNotes(e.target.value)}
                            required
                          />
                        </div>
                        <button type="submit" style={{ background: 'var(--mono-primary)' }}>
                          Execute Override
                        </button>
                      </form>
                    </div>
                  </div>
                ) : (
                  <div className="panel" style={{ padding: '3rem', textAlign: 'center' }}>
                    <FileText size={48} style={{ color: 'var(--mono-text)', margin: '0 auto 1rem', display: 'block' }} />
                    <h3>Select a claim from the registry to view details and assign adjusting ownership.</h3>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: User Directory */}
          {currentTab === 'users' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px' }}>
              <div className="panel">
                <h2>User Roles Directory</h2>
                {userDirBanner.text && (
                  <div style={{
                    padding: '12px 16px',
                    marginBottom: '14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: '600',
                    background: userDirBanner.type === 'error' ? '#fef2f2' : '#f0fdf4',
                    color: userDirBanner.type === 'error' ? '#991b1b' : '#166534',
                    border: `1px solid ${userDirBanner.type === 'error' ? '#fecaca' : '#bbf7d0'}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>{userDirBanner.text}</span>
                      <button 
                        type="button"
                        onClick={() => setUserDirBanner({ text: '', type: '', resetUrl: '' })}
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px', color: 'inherit', padding: '0 4px' }}
                      >
                        ✕
                      </button>
                    </div>
                    {userDirBanner.resetUrl && (
                      <div style={{ background: '#ffffff', border: '1px solid #bbf7d0', padding: '8px 12px', borderRadius: '6px', marginTop: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#334155', fontWeight: 'bold', marginBottom: '4px' }}>🔗 Generated Password Reset Link:</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <input 
                            readOnly 
                            value={userDirBanner.resetUrl}
                            style={{ flex: 1, padding: '4px 8px', fontSize: '11px', fontFamily: 'monospace', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#f8fafc' }}
                          />
                          <a 
                            href={userDirBanner.resetUrl} 
                            target="_blank" 
                            rel="noreferrer"
                            style={{ padding: '4px 10px', fontSize: '11px', background: '#2563eb', color: '#fff', borderRadius: '4px', textDecoration: 'none', fontWeight: 'bold' }}
                          >
                            Open Link ↗
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {/* SECTION 1: System Administrators Directory */}
                <h3 style={{ fontSize: '13px', textTransform: 'uppercase', color: '#9333ea', marginTop: '1rem', marginBottom: '0.5rem' }}>🛡️ System Administrators Directory</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', marginBottom: '1.5rem', tableLayout: 'fixed' }}>
                  <thead>
                    <tr style={{ background: 'var(--mono-surface-dark)', borderBottom: '2px solid var(--mono-text-dark)' }}>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>User ID</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '18%' }}>Username</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '16%' }}>Full Name</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '20%' }}>Email</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>Staff Role</th>
                      <th style={{ padding: '8px', textAlign: 'right', width: '18%' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allUsers.filter(u => u.role === 'admin').map((u) => (
                      <tr key={u.id} style={{ borderBottom: '1px solid var(--mono-surface-dark)' }}>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.customer_id}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.username}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.full_name}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{formatEmail(u.email)}</td>
                        <td style={{ padding: '8px', overflow: 'hidden' }}>
                          <select 
                            value={u.role}
                            onChange={(e) => handleUserRoleUpdate(u.id, e.target.value)}
                            style={{ width: '100%', maxWidth: '85px', padding: '2px 4px', fontSize: '11px', fontWeight: 'bold' }}
                          >
                            <option value="admin">ADMIN</option>
                            <option value="adjuster">ADJUSTER</option>
                          </select>
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                            <button onClick={() => handleDeleteUser(u.id, u.username)} style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-danger)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                              Delete
                            </button>
                            <button onClick={() => handleResetPassword(u.id, u.username)} style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-secondary)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                              Reset
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* SECTION 2: Claims Adjusters Directory */}
                <h3 style={{ fontSize: '13px', textTransform: 'uppercase', color: 'var(--mono-primary)', marginBottom: '0.5rem' }}>⚖️ Claims Adjusters Directory</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', marginBottom: '1.5rem', tableLayout: 'fixed' }}>
                  <thead>
                    <tr style={{ background: 'var(--mono-surface-dark)', borderBottom: '2px solid var(--mono-text-dark)' }}>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>User ID</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '18%' }}>Username</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '16%' }}>Full Name</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '20%' }}>Email</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>Staff Role</th>
                      <th style={{ padding: '8px', textAlign: 'right', width: '18%' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allUsers.filter(u => u.role === 'adjuster').map((u) => (
                      <tr key={u.id} style={{ borderBottom: '1px solid var(--mono-surface-dark)' }}>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.customer_id}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.username}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.full_name}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{formatEmail(u.email)}</td>
                        <td style={{ padding: '8px', overflow: 'hidden' }}>
                          <select 
                            value={u.role}
                            onChange={(e) => handleUserRoleUpdate(u.id, e.target.value)}
                            style={{ width: '100%', maxWidth: '85px', padding: '2px 4px', fontSize: '11px', fontWeight: 'bold' }}
                          >
                            <option value="adjuster">ADJUSTER</option>
                            <option value="admin">ADMIN</option>
                          </select>
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                            <button 
                              onClick={() => {
                                setFilterAdjusterId(u.id);
                                setFilterCustId('');
                                setFilterClaimantName('');
                                setFilterClaimId('');
                                setCurrentTab('claims');
                              }}
                              style={{ padding: '2px 6px', fontSize: '11px', background: '#2563eb', color: '#fff', border: 'none', cursor: 'pointer' }}
                            >
                              Claims
                            </button>
                            <button onClick={() => handleDeleteUser(u.id, u.username)} style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-danger)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                              Delete
                            </button>
                            <button onClick={() => handleResetPassword(u.id, u.username)} style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-secondary)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                              Reset
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* SECTION B: Policyholders / Customers Directory */}
                <h3 style={{ fontSize: '13px', textTransform: 'uppercase', color: 'var(--mono-text-dark)', marginBottom: '0.5rem' }}>👥 Customer Accounts Directory</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', tableLayout: 'fixed' }}>
                  <thead>
                    <tr style={{ background: 'var(--mono-surface-dark)', borderBottom: '2px solid var(--mono-text-dark)' }}>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>User ID</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '18%' }}>Username</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '16%' }}>Full Name</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '20%' }}>Email</th>
                      <th style={{ padding: '8px', textAlign: 'left', width: '14%' }}>Role</th>
                      <th style={{ padding: '8px', textAlign: 'right', width: '18%' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allUsers.filter(u => u.role === 'customer').map((u) => (
                      <tr key={u.id} style={{ borderBottom: '1px solid var(--mono-surface-dark)' }}>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.customer_id}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.username}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.full_name}</td>
                        <td style={{ padding: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{formatEmail(u.email)}</td>
                        <td style={{ padding: '8px' }}>
                          <span style={{ padding: '2px 6px', background: '#e2e8f0', color: '#334155', fontWeight: 'bold', fontSize: '11px', borderRadius: '3px' }}>
                            CUSTOMER
                          </span>
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                            <button 
                              onClick={() => {
                                setFilterCustId(u.customer_id || '');
                                setFilterClaimantName(u.full_name || u.username || '');
                                setCurrentTab('claims');
                              }}
                              style={{ padding: '2px 6px', fontSize: '11px', background: '#2563eb', color: '#fff', border: 'none', cursor: 'pointer' }}
                            >
                              Claims
                            </button>
                            <button 
                              onClick={() => handleDeleteUser(u.id, u.username)}
                              style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-danger)', color: '#fff', border: 'none', cursor: 'pointer' }}
                            >
                              Delete
                            </button>
                            <button 
                              onClick={() => handleResetPassword(u.id, u.username)}
                              style={{ padding: '2px 6px', fontSize: '11px', background: 'var(--mono-secondary)', color: '#fff', border: 'none', cursor: 'pointer' }}
                            >
                              Reset
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Create Employee Box */}
              <form className="panel claim-form" onSubmit={handleCreateEmployee} style={{ gridArea: 'auto' }}>
                <h2>Provision Employee Profile</h2>
                {empSuccessMsg && <div className="status-pill" style={{ display: 'block', width: '100%', marginBottom: '12px', background: '#dcfce7', color: '#166534' }}>{empSuccessMsg}</div>}
                
                <div className="input-group">
                  <label>Full Name</label>
                  <input 
                    placeholder="e.g. Sarah Adams"
                    value={empName}
                    onChange={(e) => handleEmpNameChange(e.target.value)}
                    required
                  />
                </div>

                <div className="input-group">
                  <label>Assigned Username (Set by Admin)</label>
                  <input 
                    placeholder="e.g. saadams"
                    value={empUsername}
                    onChange={(e) => setEmpUsername(e.target.value)}
                    required
                  />
                  <small style={{ fontSize: '10px', color: 'var(--mono-text-light)', marginTop: '2px', display: 'block' }}>
                    Auto-suggested rule: First 2 letters of first name + last name (editable by Admin)
                  </small>
                </div>

                <div className="input-group">
                  <label>Email address</label>
                  <input 
                    type="email"
                    placeholder="name@company.com"
                    value={empEmail}
                    onChange={(e) => setEmpEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="input-group">
                  <label>Employee Role</label>
                  <select 
                    value={empRole} 
                    onChange={(e) => setEmpRole(e.target.value)}
                  >
                    <option value="adjuster">Claims Adjuster</option>
                    <option value="admin">System Administrator</option>
                  </select>
                </div>

                <button type="submit" style={{ background: 'var(--mono-primary)' }}>
                  Create Employee
                </button>
              </form>
            </div>
          )}

          {/* TAB 3: System Audit Logs */}
          {currentTab === 'audit' && (
            <div className="panel">
              <h2>System Audit History Logs</h2>
              <div style={{ maxHeight: '60vh', overflowY: 'auto', marginTop: '1rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: 'var(--mono-surface-dark)', borderBottom: '2px solid var(--mono-text-dark)' }}>
                      <th style={{ padding: '8px', textAlign: 'left' }}>Timestamp</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>Operator</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>Action Event</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>Metadata Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid var(--mono-surface-dark)' }}>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)' }}>{new Date(log.created_at).toLocaleString()}</td>
                        <td style={{ padding: '8px' }}>{log.user ? `${log.user.full_name} (${log.user.role === 'admin' ? 'Admin' : log.user.role === 'adjuster' ? 'Employee' : 'User'})` : 'System'}</td>
                        <td style={{ padding: '8px', fontWeight: 'bold', color: 'var(--mono-secondary)' }}>{log.action}</td>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>{log.details}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: Analytics */}
          {currentTab === 'analytics' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                <div className="panel" style={{ textAlign: 'center' }}>
                  <span className="eyebrow">Total System Claims</span>
                  <strong style={{ fontSize: '28px', display: 'block', marginTop: '8px' }}>{analytics.total}</strong>
                </div>
                <div className="panel" style={{ textAlign: 'center', borderColor: 'var(--mono-success)' }}>
                  <span className="eyebrow" style={{ color: 'var(--mono-success)' }}>Claims Approved</span>
                  <strong style={{ fontSize: '28px', display: 'block', marginTop: '8px', color: 'var(--mono-success)' }}>{analytics.approved}</strong>
                </div>
                <div className="panel" style={{ textAlign: 'center', borderColor: 'var(--mono-warning)' }}>
                  <span className="eyebrow" style={{ color: 'var(--mono-warning)' }}>In Review Queue</span>
                  <strong style={{ fontSize: '28px', display: 'block', marginTop: '8px', color: 'var(--mono-warning)' }}>{analytics.underReview}</strong>
                </div>
                <div className="panel" style={{ textAlign: 'center', borderColor: 'var(--mono-secondary)' }}>
                  <span className="eyebrow" style={{ color: 'var(--mono-secondary)' }}>Average Risk Score</span>
                  <strong style={{ fontSize: '28px', display: 'block', marginTop: '8px', color: 'var(--mono-secondary)' }}>{analytics.avgRiskScore} / 100</strong>
                </div>
              </div>

              {/* Per-User Claims Analytics & Risk Graphs */}
              <div className="panel">
                <h3 style={{ fontSize: '14px', textTransform: 'uppercase', marginBottom: '1rem' }}>Per-User Claims Analytics & Risk Graphs</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {(() => {
                    const userGroupMap = {};
                    claims.forEach(c => {
                      const name = c.claimant_name || c.user?.full_name || 'Anonymous Policyholder';
                      if (!userGroupMap[name]) {
                        userGroupMap[name] = { name, total: 0, approved: 0, rejected: 0, inReview: 0, scores: [] };
                      }
                      userGroupMap[name].total += 1;
                      if (c.status === 'APPROVED') userGroupMap[name].approved += 1;
                      else if (c.status === 'REJECTED') userGroupMap[name].rejected += 1;
                      else userGroupMap[name].inReview += 1;
                      if (c.risk_score !== null && c.risk_score !== undefined) {
                        userGroupMap[name].scores.push(c.risk_score);
                      }
                    });

                    const userStats = Object.values(userGroupMap);
                    if (userStats.length === 0) {
                      return <p className="muted">No user claims registered yet.</p>;
                    }

                    return userStats.map((u, idx) => {
                      const avgScore = u.scores.length > 0 ? Math.round(u.scores.reduce((a, b) => a + b, 0) / u.scores.length) : 50;
                      const approvalRate = Math.round((u.approved / u.total) * 100);
                      const barColor = avgScore >= 70 ? 'var(--mono-success)' : avgScore >= 50 ? 'var(--mono-warning)' : 'var(--mono-danger)';

                      return (
                        <div key={idx} style={{ border: '1px solid var(--mono-surface-dark)', padding: '12px', background: 'var(--mono-surface)', borderRadius: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <strong style={{ fontSize: '13px' }}>👤 Policyholder: {u.name}</strong>
                            <span style={{ fontSize: '11px', color: 'var(--mono-text-light)' }}>Total Claims: {u.total} ({u.approved} Approved, {u.inReview} Review, {u.rejected} Rejected)</span>
                          </div>
                          
                          {/* Visual Graph Bar for Trust Score */}
                          <div style={{ marginBottom: '6px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '2px' }}>
                              <span>Average Trust Score Bar</span>
                              <span style={{ fontWeight: 'bold', color: barColor }}>{avgScore} / 100</span>
                            </div>
                            <div style={{ width: '100%', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ width: `${avgScore}%`, height: '100%', background: barColor, transition: 'width 0.3s ease' }} />
                            </div>
                          </div>

                          {/* Approval Rate Visual Meter */}
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '2px' }}>
                              <span>Historical Approval Rate</span>
                              <span style={{ fontWeight: 'bold', color: 'var(--mono-primary)' }}>{approvalRate}%</span>
                            </div>
                            <div style={{ width: '100%', height: '6px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ width: `${approvalRate}%`, height: '100%', background: 'var(--mono-primary)', transition: 'width 0.3s ease' }} />
                            </div>
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
