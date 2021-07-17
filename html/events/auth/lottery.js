reset_state();

function on_lottery_load(lotteries)
{
  $("#lottery-container").empty();
  for (const [name, lottery] of Object.entries(lotteries))
  {
    var no_users = 0;
    const grow_ratio = 1 - ( (+new Date/1000) - lottery['started_at'] ) / lottery['start_in'];
    $("#lottery-container").append(lottery_container = $(`
    <div class="d-flex flex-column m-2 p-1 mb-4 border">
      <p class='m-2'>${name}</p>
      <div class="d-flex border flex-column m-2 p-3 lottery-userlist">
      </div>
      <div class="d-flex flex-grow-1 time-container">
        <div class="time-bar">
        </div>
        <div class="time-bar-opp">
        </div>
      </div>
    </div>
      `));
    lottery_container.children("div.time-container").css({
      "height": "0.4em"
    }).children(".time-bar").css({
      "height": "0.4em",
      "background-color": "hsla(112, 58%, 83%, 1)",
      "flex-grow": grow_ratio
    }).parent().children(".time-bar-opp").css({
      "flex-grow": 1 - grow_ratio,
      "background-color": "#dee2e6"
    });
    console.log(lottery);
    for (const [jackpot_name, users] of Object.entries(lottery['enrolled_users']))
    {
      for (const [username, info] of Object.entries(users))
      {
        no_users++;
        lottery_container.children("div.lottery-userlist").append(`
        <small class='text-muted'>${jackpot_name}: ${username}, numbers: <b>${info['numbers'].join(" ")}</b></small>
          `);
      }
    }
    if (!no_users)
    {
      lottery_container.children("div.lottery-userlist").html(`
      <small class='text-muted'>there are no users participating in this lottery</small>
        `);
    }
  }
}

$("#main_container").empty().append(
  $("<p class='lead m-3 mb-0'>").text("Participate in multi-tier lotteries; win incrementally larger prizes. Take a shot at our provably fair lottery and win large by entering a jackpot, after which you will be automatically entered with chances to win proportional to how much money you staked in jackpot."),
  $("<div id='lottery-container' class='mt-3 p-2 mb-3'>").append(
    $("<small class='text-muted'>").text("loading lotteries...")
  ),
);

window.lottery_refresh = setInterval(function() {
  if (!$("#lottery-container").length)
  {
    console.log("stopping lottery refresh");
    return clearInterval(window.lottery_refresh);
  }
  console.log("refreshing lotteries");
  window.ws.send(JSON.stringify({
    action: "load_lotteries"
  }));
}, 1000);
