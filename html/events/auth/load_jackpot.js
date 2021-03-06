var user_colormap = {};
var current_bet = null;

function on_jackpot_refresh(jackpot)
{
  load_jackpot(jackpot);
}

function on_jackpot_bet(bet)
{
  /*
   * amount:
   *  local, btc, eth
   */

  $("#place-bet-btn").text("Modify bet");
  current_bet = bet['amount']['local'];
}

function on_jackpot_finish(results)
{
  /*
   * winner, seed, self
   */

  $("#place-bet-btn").prop("disabled", true);
  $("#server-seed").val(results.seed);
  if (results['self'])
  {
    display_notif("You won the jackpot, congrats!", "success");
  } else
  {
    display_notif(results.winner + " won, try again next time", "error");
  }
  setTimeout(function() {
    window.ws.send(JSON.stringify({
      action: "view_jackpot"
    }))
  }, 2000);
}

function load_jackpot(jackpot)
{
  /* enrolled_users: {test_acc_1: null},
   * jackpot_uid: "db0101fe-d858-11eb-9d00-09002bea9225"
   * start_in: 20
   * started_at: 1624916170.79311
   */

  if (jackpot['started_at'] !== null)
  {
    var current_timestamp = (new Date / 1000) >> 0;
    var time_since_start  = current_timestamp - jackpot['started_at'];
    if (time_since_start > jackpot['start_in'])
    {
      $("#wait-time-completed").css({"flex-grow": 0});
      clearInterval(window.jackpot_refresh);
      return window.ws.send(JSON.stringify({
        action: "jackpot_results",
        id: jackpot['jackpot_uid'],
        name: "$$jackpot_name"
      }));
    }
    $("#wait-time-completed").css({
      "flex-grow": 1 - time_since_start / jackpot['start_in']
    });
  }

  $("#jackpot-bet-userlist").empty();
  $("#jackpot-bets").empty().append(
    $("<p class='lead'>").text("Bet list")
      .css({"text-align": "center"})
  );

  var total_jackpot = 0;
  var total_users = 0;
 
  if (jackpot['enrolled_users'] === undefined)
  {
    jackpot = jackpot["$$jackpot_name"];
  }
  
  for (const [_, bet_amount] of Object.entries(jackpot['enrolled_users']))
  {
    if (bet_amount === null) { continue; }
    total_jackpot += bet_amount;
    total_users++;
  }

  for (const [username, bet_amount] of Object.entries(jackpot['enrolled_users']))
  {
    if (user_colormap[username] !== undefined)
    {
      var color = user_colormap[username];
    } else
    {
      var color = "#000000".replace(/0/g,function(){return (~~(Math.random()*16)).toString(16);});
      user_colormap[username] = color;
    }
     $("#jackpot-bet-userlist").append(`
    <div class="jackpot-user-bet"
        style="
          flex-grow: ` + (bet_amount / total_jackpot) + `;
          background-color: ` + color + `;
          height: 1em;
          ">
    </div>
      `);

    if (bet_amount !== null)
    {
      $("#jackpot-bets").append($("<small class='text-muted ml-2 pl-1'>").text(username + ": $" + bet_amount).css({
        "border-left": ".5em solid" + color
      }));
    }
  }

  $("#jackpot-info").empty().append([
    $("<small>").text("The total jackpot is $" + total_jackpot + ", but the house takes 5%, so you'd win $" + (((total_jackpot * 95) >> 0) / 100)),
    (current_bet !== null && total_users > 1)? $("<small>").text("Your chance of winning is " + ( ((current_bet / total_jackpot * 10000) >> 0) / 100 ) + "%") : "",
    (current_bet !== null)? $("<small>").text("Regardless of whether you win or not, you will win " + current_bet * 2.5 + " XP and $" + current_bet + " into clearing"): ""
  ]);

  if (!total_users)
  {
    $("#jackpot-bet-userlist").append($("<small class='text-muted m-3'>").text(
      "No users currently entered"
    ));
  }

  if (!total_jackpot)
  {
    $("#jackpot-bets").append($("<small class='m-3 text-muted'>").text("No bets active"));
  }
}

reset_state();

$("#main_container").empty().append(`
<p class="lead p-3">$$jackpot_name</p>
<div id="jackpot-bet-visual" class="d-flex flex-column flex-grow border ml-2 mr-2">
  <div id="jackpot-bet-userlist" class="d-flex flex-grow">
    <small class='text-muted m-3'>loading bets...</small>
  </div>
  <div id="wait-time" class="d-flex flex-grow-1"
      style="background-color: #dee2e6; height: 0.4em;">
      <div id="wait-time-completed"
          style="background-color: hsla(112, 58%, 83%, 1);">
      </div>
      <div class="flex-shrink-1">
      </div>
  </div>
</div>
<div id="jackpot-container" class="d-flex mt-3">
  <div id="jackpot-bets" class="d-flex flex-column border ml-2 p-2">
    <small class='text-muted m-3'>loading bet list...</small>
  </div>
  <div id="jackpot-control" class="flex-grow-1 ml-3 mr-3">
    <div id="jackpot-form" class="d-flex flex-column border-bottom mb-2 pb-2">

      <div class="input-group mb-3">
        <div class="input-group-prepend">
          <span class="input-group-text">$</span>
        </div>
        <input id="bet-amount" type="text" class="form-control">
        <div class="input-group-append">
          <button class="btn enter-btn btn-outline-primary" type="button" style="
              border-top-left-radius: 0;
              border-bottom-left-radius: 0;
              " id="place-bet-btn">
            Place bet
          </button>
        </div>
      </div>

      <div class="input-group mb-3">
        <div class="input-group-prepend">
          <span class="input-group-text">Client seed</span>
        </div>
        <input id="client-seed" type="text" class="form-control">
      </div>

      <div class="input-group mb-3">
        <div class="input-group-prepend">
          <span class="input-group-text">Server seed</span>
        </div>
        <input id="server-seed" type="text" class="form-control" disabled>
      </div>

      <button type="button" id="leave-btn" class="ml-auto btn btn-outline-danger">Leave</button>

    </div>
    <div id="jackpot-info" class="d-flex flex-column">
      <small class='text-muted m-3'>loading active bet info...</small>
    </div>
  </div>
</div>
`);

load_jackpot($$jackpot);
$("#server-seed").val("$$server_seed");

$("#place-bet-btn").click(function() {
  window.ws.send(JSON.stringify({
    action: "place_bet",
    name: "$$jackpot_name",
    amount: $("#bet-amount").val(),
    seed: $("#client-seed").val()
  }));
  $(this).prop("disabled", true);
  setTimeout(function() {
    $("#place-bet-btn").prop("disabled", false);
  }, 1000);
});

$("#leave-btn").click(function() {
  console.log("sending jackpot leave");
  window.ws.send(JSON.stringify({
    action: "leave_jackpot",
    name: "$$jackpot_name"
  }));
  setTimeout(function() {
    window.ws.send(JSON.stringify({
      action: "event_handler",
      name: "home"
    }));
  }, 500);
});

clearInterval(window.jackpot_refresh);

window.jackpot_refresh = setInterval(function() {
  if (!$("#jackpot-container").length) {
    return clearInterval(window.jackpot_refresh);
  }
  console.log("in load jackpot $$jackpot_name");
  window.ws.send(JSON.stringify({
    action: "refresh_jackpot",
    name: "$$jackpot_name"  /* occasionally this doesn't work for some weird reason */
  }));
}, 1500);

