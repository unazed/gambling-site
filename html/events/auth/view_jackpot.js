reset_state();

function on_jackpot_refresh(jackpots)
{

}

if (typeof $$jackpots !== "undefined") {
  var jackpots = $$jackpots;

  $("#main_container").empty().append(`
    <p class='lead m-3'>Play your odds against other people in our multi-tier jackpots</p>
    <div id="jackpot-container">
      <small class='text-muted'>loading jackpots...</small>
    </div>
  `);

  $("#jackpot-container").empty();
  for (const jackpot_name in jackpots)
  {
    jackpot = jackpots[jackpot_name];
    $("#jackpot-container").append(`
  <div class="d-flex border jackpot-item p-3 m-2" id="` + jackpot_name + `">
    <p>` + jackpot_name + `</p>
    <div class="border bet-container p-1">
    </div>
    <div class="d-flex jackpot-item-control">
      <small class='text-muted'>min. $` + jackpot['min'] + `, max. $` + jackpot['max'] + `</small>
      <button class="btn btn-outline-secondary" type="button"
          style="margin-left: auto;">
        Enter
      </button>
    </div>
  </div>
      `);
    if (!jackpot.jackpot_uid)
    {
      $("#" + jackpot_name.replace(" ", "\\ ") + " .bet-container").append(`
      <small class='text-muted'></small>
        `);
    }
  }

  window.jackpot_refresh = setInterval(function() {
    if (!$("#jackpot_container").length) {
      return clearInterval(window.jackpot_refresh);
    }
    window.ws.send(JSON.stringify({
      action: "refresh_jackpot"
    }));
  }, 500);
} else {
  window.ws.send(JSON.stringify({
    action: "view_jackpot"
  }));
}
