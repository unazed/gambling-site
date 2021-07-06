reset_state();

function on_profile(resp) {
  $("#level").empty().append(
    $("<p class='lead ml-3'>").text(resp.username),
    $("<div class='d-flex flex-grow'>").append(
      $("<div>").css({
        "flex-grow": resp.xp / (resp.xp + resp.next_level_dist),
        "background-color": "#00ff6b59",
        "height": "1em"
      }),
      $("<div>").css({
        "flex-grow": 1 - resp.xp / (resp.xp + resp.next_level_dist),
        "height": "1em",
        "background-color": "gainsboro"
      })
    ),
    $("<div class='d-flex position-relative'>").append(
      $("<small class='text-muted mt-1 ml-1'>").text(resp.next_level_dist + " XP left to level " + (resp.level + 1)).append(
        $("<br>"), 'Lottery points: ' + resp.lottery.points
      ),
      $("<small class='text-muted'>").text(resp.xp + "/" + (resp.xp + resp.next_level_dist))
        .css({
          "position": "absolute",
          "right": ".25em",
          "top": ".25em"
        })
    )
  );

  $("#jackpots").empty().append(
    $("<table class='table table-sm' id='jackpot-table'>").append(
      $("<thead>").append(
        $("<tr>").append(
          $("<th scope='col'>").text("Date"),
          $("<th scope='col'>").text("Jackpot Name"),
          $("<th scope='col'>").text("Bet"),
          $("<th scope='col'>").text("Seed"),
          $("<th scope='col'>").text("Winner")
        )
      ),
      $("<tbody>")
    )
  );

  if (resp.jackpot === undefined)
  {
    $("#jackpots").append($("<small class='text-muted'>").text("No jackpots have been entered"));
  } else
  {
    for (const [_, jackpot] of Object.entries(resp.jackpot))
    {
      var jackpot_date = new Date(jackpot.started_at * 1000).toLocaleDateString("en-US");
      $("#jackpot-table tbody").append(
        $("<tr>").append(
          $("<td>").text(jackpot_date),
          $("<td>").text(jackpot.jackpot_name),
          $("<td>").text("$" + jackpot.enrolled_users[$$username]),
          $("<td>").text(jackpot.server_seed),
          $("<td>").text(jackpot.winner)
        )
      );
    }
  }

  $("#lotteries").empty().append(
    $("<table class='table table-sm' id='lottery-table'>").append(
      $("<thead>").append(
        $("<tr>").append(
          $("<th scope='col'>").text("Date"),
          $("<th scope='col'>").text("Lottery Name"),
          $("<th scope='col'>").text("Numbers"),
          $("<th scope='col'>").text("Client Seed"),
          $("<th scope='col'>").text("Server Seed"),
          $("<th scope='col'>").text("Winnings")
        )
      ),
      $("<tbody>")
    )
  );

  if (resp.lotteries === undefined)
  {
    return $("#lotteries").append($("<small class='text-muted'>").text("No lotteries have been entered"));
  }

  for (const [_, lottery] of Object.entries(resp.lottery.history))
  {
    var lottery_date = new Date(lottery.game_info.started_at * 1000).toLocaleDateString("en-US");
    var numbers = "";
    var winnings = 0;

    for (const number of lottery.enrolled_users[$$username].numbers)
    {
      if (lottery.numbers.includes(number))
      {
        winnings = lottery.jackpot;
      }
      numbers += number + " ";
    }

    $("#lottery-table tbody").append(
      $("<tr>").append(
        $("<td>").text(lottery_date),
        $("<td>").text(lottery.lottery_name),
        $("<td>").text(numbers),
        $("<td>").text(lottery.enrolled_users[$$username].seed),
        $("<td>").text(lottery.game_info.server_seed),
        $("<td>").text("$" + winnings)
      )
    );
  }
}

window.ws.send(JSON.stringify({
  action: "profile_info",
  username: sessionStorage.getItem("username")
}));

$("#main_container").empty().append(`
<div class="container d-flex flex-column" id="profile-container">
  <div id="level" class="d-flex flex-column border flex-grow border-bottom-0 p-3 mt-3">
    <small class='text-muted m-3'>loading username & level...</small>
  </div>
  <div class="d-flex border p-3 border-top-0" id="history-container">
    <div id="jackpots" class="d-flex flex-column flex-grow-1 overflow-auto">
      <small class="text-muted">loading jackpot history</small>
    </div>
    <div id="lotteries" class="flex-grow-1 ml-3 overflow-auto">
      <small class="text-muted">loading lottery history</small>
    </div>
  </div>
</div>
`);

if (is_mobile())
{
  $("#history-container").addClass("flex-column");
  $("#lotteries").removeClass("ml-3");
}
