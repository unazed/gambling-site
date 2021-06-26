function on_jackpot_refresh(jackpot)
{
  load_jackpot(jackpot);
}

function load_jackpot(jackpot)
{
  console.log(jackpot);
}

reset_state();

$("#main_container").empty().append(`
<p class="lead p-3">$$jackpot_name</p>
<div id="jackpot-bet-visual" class="d-flex flex-grow border ml-2 mr-2">
  <small class='text-muted m-3'>loading bets...</small>
</div>
<div id="jackpot-container" class="d-flex mt-3">
  <div id="jackpot-bets" class="d-flex flex-column border ml-2">
    <small class='text-muted m-3'>loading bet list...</small>
  </div>
  <div id="jackpot-control" class="flex-grow-1 ml-3 mr-3">
    <div id="jackpot-form" class="border-bottom mb-2 pb-2">

      <div class="input-group mb-3">
        <div class="input-group-prepend">
          <span class="input-group-text">$</span>
        </div>
        <input type="text" class="form-control">
        <div class="input-group-append">
          <button class="btn enter-btn btn-outline-primary" type="button" style="
              border-top-left-radius: 0;
              border-bottom-left-radius: 0;
              ">
            Place bet
          </button>
        </div>
      </div>

      <div class="input-group mb-3">
        <div class="input-group-prepend">
          <span class="input-group-text">Server seed</span>
        </div>
        <input id="server-seed" type="text" class="form-control" disabled>
      </div>

    </div>
    <div id="jackpot-info">
      <small class='text-muted m-3'>loading active bet info...</small>
    </div>
  </div>
</div>
`);

load_jackpot($$jackpot);
$("#server-seed").val("$$server_seed");

window.jackpot_refresh = setInterval(function() {
  if (!$("#jackpot-container").length) {
    return clearInterval(window.jackpot_refresh);
  }
  window.ws.send(JSON.stringify({
    action: "refresh_jackpot",
    name: "$$jackpot_name"
  }));
}, 500);

