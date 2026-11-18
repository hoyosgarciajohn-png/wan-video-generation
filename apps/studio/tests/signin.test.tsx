import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { render,screen,fireEvent,cleanup,waitFor } from '@testing-library/react';
import { SignIn } from '../src/SignIn';
const original=globalThis.fetch;
afterEach(()=>{ cleanup();globalThis.fetch=original;window.history.replaceState(null,'','/'); });
test('first use and recovery explain missing mail connection without claiming email sent',async()=>{
  globalThis.fetch=async()=>Response.json({recovery_ready:false});
  render(<SignIn onSignedIn={async()=>{}}/>);
  fireEvent.click(screen.getByRole('button',{name:'First time? Set your password'}));
  await screen.findByText(/Password email is not connected yet/);
  assert.equal((screen.getByRole('button',{name:'Email password link'}) as HTMLButtonElement).disabled,true);
  assert.equal(screen.queryByLabelText('Studio access token'),null);
});
test('reset strips link from address, validates confirmation and posts correct token',async()=>{
  const token='fictional-reset-link-0000000000000000';let submitted:any;
  window.history.replaceState(null,'','/#director/reset/'+token);
  globalThis.fetch=async(input,init)=>{
    if(String(input).endsWith('/reset')) submitted=JSON.parse(String(init?.body));
    return Response.json({recovery_ready:true});
  };
  render(<SignIn onSignedIn={async()=>{}}/>);
  assert.equal(window.location.hash,'#director');
  fireEvent.change(screen.getByLabelText('New password'),{target:{value:'fictional-password'}});
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'different-password'}});
  fireEvent.click(screen.getByRole('button',{name:'Save password'}));
  await screen.findByText('The passwords do not match.');assert.equal(submitted,undefined);
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'fictional-password'}});
  fireEvent.click(screen.getByRole('button',{name:'Save password'}));
  await screen.findByText('Password saved. Sign in with your email and new password.');
  assert.deepEqual(submitted,{token,password:'fictional-password'});
});
test('wrong credentials preserve form and communicate error',async()=>{
  globalThis.fetch=async(input)=>String(input).endsWith('/session')?new Response('',{status:401}):Response.json({recovery_ready:true});
  render(<SignIn onSignedIn={async()=>{throw Error('must not login');}}/>);
  fireEvent.change(screen.getByLabelText('Email'),{target:{value:'fictional@example.test'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'fictional-password'}});
  fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
  await screen.findByText('Email or password is incorrect.');
  await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Sign in'}) as HTMLButtonElement).disabled,false));
});
