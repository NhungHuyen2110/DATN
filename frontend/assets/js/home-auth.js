"use strict";
(async()=>{const link=document.querySelector('#account-link');if(!link||!window.LUMIERE_API)return;try{const user=await LUMIERE_API.me();link.href='./pages/account.html';link.title='Tài khoản: '+user.full_name;link.setAttribute('aria-label','Tài khoản '+user.full_name)}catch{link.href='./pages/login.html'}})();
