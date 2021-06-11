reset_state();
$("#main_container").empty().append($("<div class='p-3 pb-0'>").append(`
<div class="input-group mb-3">
  <div class="input-group-prepend">
    <span class="input-group-text" id="basic-addon1">gambling-site.com/profile/</span>
  </div>
  <input type="text" id="input_username" class="form-control"
    placeholder="Username" aria-label="username" aria-describedby="basic-addon1">
</div>

<div class="input-group mb-3">
  <input type="text" id="input_email" class="form-control"
    placeholder="Email" aria-label="email" aria-describedby="basic-addon1">
</div>

<div class="input-group mb-3">
  <input type="password" id="input_password" class="form-control"
    placeholder="Password">
</div>
`));

var email = $("#input_email");
var username = $("#input_username");
var password = $("#input_password");
var button = $('<button type="submit" class="m-3 mt-0 btn btn-secondary">Register</button>');

$("#main_container").append(button);
if ($$username) {
  email.prop("disabled", true);
  password.prop("disabled", true);
  username.prop("disabled", true);
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
    username.prop("disabled", true);
    password.prop("disabled", true);
    email.prop("disabled", true);

    grecaptcha.ready(function() {
      grecaptcha.execute('6LclcyUbAAAAALvjjxT5jPnnm4AXDYcJzeI6ZrNS', {action: 'submit'}).then(function(tok) {
        window.ws.send(JSON.stringify({
          action: "verify_recaptcha",
          token: tok
        }));
        setTimeout(function() {
          window.ws.send(JSON.stringify({
            action: "register",
            email: email.val(),
            username: username.val(),
            password: password.val()
          }));
        }, 1000);
      });
    });
  });
}
