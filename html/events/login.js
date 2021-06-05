reset_state();
$("#main_container").empty().append($("<div class='p-3 pb-0'>").append(`
<div class="input-group mb-3">
  <input type="text" id="input_email" class="form-control"
    placeholder="Email" aria-label="Email" aria-describedby="basic-addon1">
</div>
<div class="input-group mb-3">
  <input type="password" id="input_password" class="form-control"
    placeholder="Password">
</div>`));

var email = $("#input_email");
var password = $("#input_password");
var button = $('<button type="submit" class="m-3 mt-0 btn btn-secondary">Login</button>');

$("#main_container").append(button);
if ($$username) {
  email.prop("disabled", true);
  password.prop("disabled", true);
  button.prop("disabled", true);
  display_notif("you're already logged in", "warning");
  setTimeout(function() {
    window.ws.send(JSON.stringify({
      action: "event_handler",
      name: "home"
    }))
  }, 2000);
} else {
  $(button).click(function() {
    window.ws.send(JSON.stringify({
      action: "login",
      email: email.val(),
      password: password.val()
    }));
    email.prop("disabled", true);
    password.prop("disabled", true);
  });
}
