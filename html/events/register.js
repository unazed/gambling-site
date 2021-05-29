reset_state();
$("#main_container").empty().append(
`<div class="input-group mb-3">
  <div class="input-group-prepend">
    <span class="input-group-text" id="basic-addon1">gambling-site.com/profile/</span>
  </div>
  <input type="text" id="input_email" class="form-control"
    placeholder="Email" aria-label="email" aria-describedby="basic-addon1">
</div>
<div class="input-group mb-3">
  <input type="password" id="input_password" class="form-control"
    placeholder="Password">
</div>`);

var email = $("#input_email");
var password = $("#input_password");
var button = $('<button type="submit" class="btn btn-secondary">Register</button>');

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
    firebase.auth().createUserWithEmailAndPassword(email.val(), password.val())
      .then((userCredential) => {
        window.user_object = userCredential.user;
        display_notif("successfully registered", "success");
      })
      .catch((error) => {
        var errorCode = error.code;
        var errorMessage = error.message;
        display_notif(errorMessage, "error");
      });
  });
}
