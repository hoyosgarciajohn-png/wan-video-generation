import { useEffect, useState } from 'react';
import { StudioError } from './model';

type Props = { onSignedIn: () => Promise<void>; authenticate?: (email: string, password: string) => Promise<unknown> };
export function SignIn({ onSignedIn, authenticate }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [resetToken] = useState(() => window.location.hash.startsWith('#director/reset/') ? window.location.hash.slice(16) : '');
  const [mode, setMode] = useState<'login'|'recovery'|'reset'>(resetToken ? 'reset' : 'login');
  const [ready, setReady] = useState<boolean>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => {
    if (resetToken) window.history.replaceState(null, '', '/#director');
    void fetch('/v1/studio/auth/config', { credentials: 'same-origin' })
      .then(r => { if (!r.ok) throw Error(); return r.json(); })
      .then(c => setReady(c.recovery_ready === true))
      .catch(() => setReady(false));
  }, [resetToken]);
  function switchMode(next: 'login'|'recovery') { setMode(next); setError(''); setMessage(''); setPassword(''); setConfirm(''); }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(''); setMessage('');
    if (mode === 'reset' && password !== confirm) { setError('The passwords do not match.'); return; }
    setBusy(true);
    try {
      if (mode === 'login' && authenticate) {
        await authenticate(email,password); setPassword(''); await onSignedIn(); return;
      }
      const path = mode === 'login' ? 'session' : mode === 'recovery' ? 'auth/recovery' : 'auth/reset';
      const body = mode === 'login' ? { email, password } : mode === 'recovery' ? { email } : { token: resetToken, password };
      const r = await fetch('/v1/studio/' + path, {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-WAN-Request': 'studio' }, body: JSON.stringify(body),
      });
      if (!r.ok) {
        if (r.status === 401) throw Error('Email or password is incorrect.');
        if (r.status === 429) throw Error('Too many attempts. Please try again later.');
        if (r.status === 422 && mode === 'reset') throw Error('This link is invalid or expired. Request a new password link.');
        throw Error(mode === 'recovery' ? 'Password email is unavailable. Please contact the workspace administrator.' : 'Unable to connect. Please try again.');
      }
      setPassword(''); setConfirm('');
      if (mode === 'login') await onSignedIn();
      else if (mode === 'reset') { setMode('login'); setMessage('Password saved. Sign in with your email and new password.'); }
      else setMessage('If this email has access, a password link will arrive shortly. Check your spam folder too.');
    } catch (e) { setError(e instanceof StudioError ? (e.code === 401 ? 'Email or password is incorrect.' : e.code === 429 ? 'Too many attempts. Please try again later.' : 'Unable to connect. Please try again.') : e instanceof Error ? e.message : 'Unable to connect.'); }
    finally { setBusy(false); }
  }
  return <section className="d-card d-login">
    <h2>{mode === 'login' ? 'Sign in to your studio' : mode === 'recovery' ? 'Get a password link' : 'Choose your password'}</h2>
    <p>{mode === 'login' ? 'Your songs, characters and saved projects are waiting.' : mode === 'recovery' ? 'Use your workspace email to set your first password or reset it.' : 'Use 12–128 characters. A longer, unique passphrase works well.'}</p>
    <form className="d-auth-form" onSubmit={submit}>
      {mode !== 'reset' && <label>Email<input name="email" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={254} disabled={busy}/></label>}
      {mode !== 'recovery' && <><label>{mode === 'reset' ? 'New password' : 'Password'}<input name="password" type={show ? 'text' : 'password'} autoComplete={mode === 'reset' ? 'new-password' : 'current-password'} value={password} onChange={e=>setPassword(e.target.value)} required minLength={mode === 'reset' ? 12 : undefined} maxLength={128} disabled={busy}/></label>
      <label className="d-auth-show"><input type="checkbox" checked={show} onChange={e=>setShow(e.target.checked)}/> Show password</label></>}
      {mode === 'reset' && <label>Confirm password<input type={show ? 'text' : 'password'} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required minLength={12} maxLength={128} disabled={busy}/></label>}
      <button className="d-primary" disabled={busy || (mode === 'recovery' && ready !== true)}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : mode === 'recovery' ? 'Email password link' : 'Save password'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {mode === 'login' ? <div className="d-auth-links"><button type="button" disabled={busy} onClick={()=>switchMode('recovery')}>First time? Set your password</button><button type="button" disabled={busy} onClick={()=>switchMode('recovery')}>Forgot password?</button></div> : <button type="button" disabled={busy} onClick={()=>switchMode('login')}>Back to sign in</button>}
    {mode === 'recovery' && ready === false && <p role="status">Password email is not connected yet. Your existing projects are preserved; the administrator must finish email setup before sending your first password link.</p>}
  </section>;
}
