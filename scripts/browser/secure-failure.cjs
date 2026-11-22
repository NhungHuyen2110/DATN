// Playwright error messages may include Cookie/Authorization headers. Preserve
// details beside the protected QA fixture and publish only controlled fields.
const fs=require('node:fs'),path=require('node:path');
module.exports=function secureFailure(error,fixturePath,reportPath,phase='acceptance') {
 if(!['qa_readiness','model_readiness','customer_conversation','management_conversation','acceptance'].includes(phase)) phase='acceptance';
 let retained=false;
 const privateLog=path.join(path.dirname(fixturePath),path.basename(reportPath)+'.failure.log');
 try {fs.writeFileSync(privateLog,String(error.stack||error),{flag:'wx'});retained=true} catch {}
 const type=['Error','AssertionError','TimeoutError'].includes(error.name)?error.name:'BrowserError';
 const report={successful:false,phase,error_type:type,private_failure_log_retained:retained,
  credentials_published:false,acceptance_not_claimed:true};
 if(!fs.existsSync(reportPath)) fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 console.error(JSON.stringify(report));process.exitCode=1;
};
