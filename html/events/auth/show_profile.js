reset_state();

function on_profile(resp) {
  console.log("on_profile", resp);
}

window.ws.send(JSON.stringify({
  action: "profile_info",
  username: sessionStorage.getItem("username")
}));

$("#main_container").empty().append(
);
