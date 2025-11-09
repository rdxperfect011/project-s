// Small behaviour: confirm file size (optional)
document.addEventListener('DOMContentLoaded', function(){
  const receiptInput = document.querySelector('input[name="receipt"]');
  if (receiptInput){
    receiptInput.addEventListener('change', function(e){
      const f = e.target.files[0];
      if (f && f.size > 5 * 1024 * 1024) { // 5MB
        alert("Receipt appears larger than 5MB. Consider compressing the image or uploading a PDF.");
      }
    });
  }
});