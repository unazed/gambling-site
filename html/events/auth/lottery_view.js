reset_state();

var started = false;

function on_lottery_update(data) {
  if (!started) { started = true; }
  time_to_start = (( ( data.active.game_info.start_in - ( ( (+new Date / 1000) >> 0 ) - data.active.game_info.started_at ) ) * 100 ) >> 0) / 100;
  jackpot = data.templ.jackpot;

  $("#lottery-status-bar").empty().append(
    $("<span>").text("Jackpot: $" + jackpot),
    data.active.is_active?
      $("<span>").text("Starts in " + time_to_start + " second(s)")
        .css({
          "float": "right"
        })
    : $("<span>").text("Lottery finished").css({"float": "right"})
  );
  $("#lottery-userlist").empty();
  for (const username in data.active.enrolled_users)
  {
    $("#lottery-userlist").append($("<li class='list-group-item'>").text(username)
      .css({"background-color": "transparent"}));
  }
  $("#lottery-numbers").empty().append(`
  <span>Your roll</span>
  <div class='d-flex' id="own-numbers">
    <small class='ml-3 text-muted'>loading your numbers...</small>
  </div>
  <span>Server's roll</span>
  <div class='d-flex' id="server-numbers">
    <small class='ml-3 text-muted'>the server hasn't yet rolled</small>
  </div>
    `);

  if (!data.active.is_active)
  {
    clearInterval(window.lottery_intervals["$$lottery"]);
    $("#client-seed").prop("disabled", true);
    $("#client-seed-update-btn").prop("disabled", true);
    $("#server-numbers").empty();
    for (const number of data.active.numbers) {
      $("#server-numbers").append(`
        <p class='ml-3'>` + number + `</p>
        `);
    }
    $("#server-seed").val(data.active.game_info.server_seed);
  }

  $("#own-numbers").empty();
  for (const number of data.active.enrolled_users["$$username"].numbers) {
    $("#own-numbers").append(`
      <p class='ml-3'>` + number + `</p>
      `);
  }
}

$("#main_container").empty().append(`
<h3 class='m-3'>$$lottery</h3>
<div class='d-flex m-3' id='lottery-container'>
  <div class='d-flex border' id='lottery-view'>
    <div class='p-2' id='lottery-numbers'>
      loading lottery numbers...
    </div>
    <div class='border-left p-2' id='lottery-users'>
      <p>Users</p>
      <ul id='lottery-userlist' class="list-group list-group-flush">
      </ul>
    </div>
  </div>
  <div class='border-top-0 border p-2' id='lottery-status-bar'>
    loading status bar...
  </div>
</div>

<div id='lottery-input'>
  <div id='` + (is_mobile()? "lottery-seed-mobile": "lottery-seed") + `' class="d-flex ml-4">

    <div class="input-group mb-3">
      <div class="input-group-prepend">
        <span class="input-group-text">Client seed</span>
      </div>
      <input type="text" class="form-control" id="client-seed">
      <div class="input-group-append">
        <button class="btn btn-outline-secondary" type="button"
          id="client-seed-update-btn">Update</button>
      </div>
    </div>

    <div class="input-group mb-3">
      <div class="input-group-prepend">
        <span class="input-group-text">Server seed</span>
      </div>
      <input type="text" class="form-control" id="server-seed" disabled>
    </div>

  </div>
  <button id='lottery-leave-btn' type="button" class="btn btn-outline-danger mr-4">Leave lottery</button>
</div>
`);

$("#client-seed").val("$$clientseed");
$("#server-seed").val("$$seed");

$("#client-seed-update-btn").click(function() {
  if (!started)
  {
    return display_notif("lottery hasn't started yet", "warning");
  }
  window.ws.send(JSON.stringify({
    action: "lottery_clientseed",
    seed: $("#client-seed").val(),
    name: "$$lottery"
  }));
});

$("#lottery-leave-btn").click(function() {
  if (!started)
  {
    return display_notif("lottery hasn't started yet", "warning");
  }
  window.ws.send(JSON.stringify({
    action: "leave_lottery",
    name: "$$lottery"
  }));
});

window.lottery_intervals["$$lottery"] = setInterval(function() {
  window.ws.send(JSON.stringify({
    action: "lottery_heartbeat",
    name: "$$lottery"
  }));
}, 250);
