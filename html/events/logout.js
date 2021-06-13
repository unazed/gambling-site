window.sessionStorage.removeItem("username");
window.sessionStorage.removeItem("token");

console.log(window.check_confirmation);
if (window.check_confirmation !== undefined)
{
  for (const tx_id in window.check_confirmation)
  {
    clearInterval(window.check_confirmation[tx_id]);
  }
}
