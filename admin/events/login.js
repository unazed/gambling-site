function event_main()
{
  $("#content-container").html(`
  <div class="d-flex flex-column align-self-center mx-auto border p-3">
    <small class='text-muted mb-3'>
      All actions performed here are logged, and monitored
      for safety purposes
    </small>
    <div class="input-group mb-3">
      <div class="input-group-prepend">
        <span class="input-group-text">Username</span>
      </div>
      <input type="text" class="form-control" id="username">
    </div>
    <div class="input-group">
      <div class="input-group-prepend">
        <span class="input-group-text">Password</span>
      </div>
      <input type="password" class="form-control" id="password">
      <div class="input-group-append">
        <button class="btn btn-outline-secondary" type="button"
          id="login-btn">Login</button>
      </div>
    </div>
  </div>`);

  $("#login-btn").click(function() {
    const username = $("#username").val(),
          password = $("#password").val();
    notify("info", "Attempting to log in...");
    return post_message({
      action: "login",
      username: username,
      password: password
    });
  });
}
