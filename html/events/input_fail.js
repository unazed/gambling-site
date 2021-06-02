username = $("#input_username");
password = $("#input_password");
email = $("#input_email");

if ($$object !== null) {
  $$object.addClass("is-invalid");
}
display_notif($$reason, "error");

username.prop("disabled", false);
password.prop("disabled", false);
email.prop("disabled", false);
