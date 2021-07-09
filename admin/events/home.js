var currently_active_action = null;
var currently_active_user = null;
var currently_active_withdrawal = null;

function reset_active_state()
{
  currently_active_withdrawal = null;
}

$.extend(true, EVENT_CALLBACKS, {
  on_view_profile: function(user) {
    console.log(user);
    $("#user-information").html(`
    <p class='lead'>Email: ${user.profile.email}</p>
    <p class='lead'>Level: ${user.profile.level} (XP: ${user.profile.xp})</p>
    <p class='lead'>Cleared funds: $${user.profile.cleared}</p>
    <p class='lead'>Lottery points: ${user.profile.lottery.points}</p>
      `);
  },
  on_view_withdrawals: function(user) {
    if (user['withdrawals'] === null)
    {
      return $("#user-information").html(`
      <p class='lead'>No withdrawal information exists</p>
        `);
    }
    const withdrawals = Object.entries(user.withdrawals);
    $("#user-information").html(`
    <p>Select any row to modify the withdrawal</p>
    <table class="table table-sm" id="withdrawal-table">
      <thead>
        <tr>
          <th scope="col">Timestamp</th>
          <th scope="col">Currency</th>
          <th scope="col">Address</th>
          <th scope="col">Amount</th>
          <th scope="col">Amount (USD)</th>
          <th scope="col">Validated*</th>
        </tr>
      </thead>
      <tbody>
      </tbody>
    </table>
    <div class="d-none pt-2 mt-2 mb-3 border-top" id="withdrawal-action">
      <button type="button" class="ml-3 mt-2 btn btn-outline-primary" id="validate-btn">Validate/Invalidate</button>
      <button type="button" class="ml-3 mt-2 btn btn-outline-primary" id="remove-btn">Remove</button>
    </div>
    <small class='text-muted'>* if a withdrawal is validated, it means it has been registered as successful</small>
      `);
    for (const [uid, withdrawal] of withdrawals)
    {
      $("#withdrawal-table tbody").append(row = $(`
      <tr>
        <th scope="row">${withdrawal.created_at}</th>
        <td>${withdrawal.currency}</td>
        <td>${withdrawal.address}</td>
        <td>${withdrawal.pricing[withdrawal.currency]}</td>
        <td>$${withdrawal.pricing.local}</td>
        <td>${withdrawal.validated? "yes": "no"}</td>
      </tr>
        `));
      row.click(function() {
        if (currently_active_withdrawal === null)
          { $("#withdrawal-action").removeClass("d-none"); }
        else
          { currently_active_withdrawal.removeClass("withdrawal-selected"); }
        currently_active_withdrawal = $(this).addClass("withdrawal-selected");

        $("#validate-btn").click(function() {
          post_message({
            action: "validate_withdrawal",
            username: user.profile.username,
            uid: uid
          });
          setTimeout(function() {
            reset_active_state();
            return post_message({
              action: "load_action",
              username: user.profile.username,
              name: "view-withdrawals",
            });
          }, 500);
        }).text(withdrawal.validated? "Invalidate": "Validate");

        $("#remove-btn").click(function() {
          post_message({
            action: "remove_withdrawal",
            username: user.profile.username,
            uid: uid
          });
          setTimeout(function() {
            reset_active_state();
            return post_message({
              action: "load_action",
              username: user.profile.username,
              name: "view-withdrawals",
            });
          }, 500);
        });
      });
    }
  },
  on_view_deposits: function(user) {
    if (user['deposits'] === null)
    {
      return $("#user-information").html(`
      <p class='lead'>No deposit information exists</p>
        `);
    }
    const deposits = Object.entries(user.deposits);
    $("#user-information").html(`
    <p>Select any row to modify the deposit</p>
    <table class="table table-sm" id="deposit-table">
      <thead>
        <tr>
          <th scope="col">Timestamp</th>
          <th scope="col">Currency</th>
          <th scope="col">Recv. Address</th>
          <th scope="col">Amount</th>
          <th scope="col">Amount (USD)</th>
          <th scope="col">Validated*</th>
        </tr>
      </thead>
      <tbody>
      </tbody>
    </table>
    <div class="d-none pt-2 mt-2 mb-3 border-top" id="deposit-action">
      <button type="button" class="ml-3 mt-2 btn btn-outline-primary" id="validate-btn">Validate/Invalidate</button>
      <button type="button" class="ml-3 mt-2 btn btn-outline-primary" id="remove-btn">Remove</button>
    </div>
    <small class='text-muted'>* if a deposit is validated, it means it has been registered as successful</small>
      `);
    for (const [uid, deposit] of deposits)
    {
      $("#deposit-table tbody").append(row = $(`
      <tr>
        <th scope="row">${deposit.created_at}</th>
        <td>${deposit.requested_currency}</td>
        <td>${deposit.addresses[deposit.requested_currency]}</td>
        <td>${deposit.pricing[deposit.requested_currency].amount}</td>
        <td>$${deposit.pricing.local.amount}</td>
        <td>${deposit.validated? "yes": "no"}</td>
      </tr>
        `));
      row.click(function() {
        if (currently_active_withdrawal === null)
          { $("#deposit-action").removeClass("d-none"); }
        else
          { currently_active_withdrawal.removeClass("deposit-selected"); }
        currently_active_withdrawal = $(this).addClass("deposit-selected");

        $("#validate-btn").click(function() {
          post_message({
            action: "validate_deposit",
            username: user.profile.username,
            uid: uid
          });
          setTimeout(function() {
            reset_active_state();
            return post_message({
              action: "load_action",
              username: user.profile.username,
              name: "view-deposits",
            });
          }, 500);
        }).text(deposit.validated? "Invalidate": "Validate");

        $("#remove-btn").click(function() {
          post_message({
            action: "remove_deposit",
            username: user.profile.username,
            uid: uid
          });
          setTimeout(function() {
            reset_active_state();
            return post_message({
              action: "load_action",
              username: user.profile.username,
              name: "view-deposits",
            });
          }, 500);
        });
      });
    }

  },
  on_view_lotteries: function(user) {
    if (user.profile.lottery['history'] === undefined)
    {
      return $("#user-information").html(`
      <p class='lead'>No lottery information exists</p>
        `);
    }
    const lotteries = Object.values(user.profile.lottery.history);
    $("#user-information").html(`
    <table class="table table-sm" id="lottery-table">
      <thead>
        <tr>
          <th scope="col">Timestamp</th>
          <th scope="col">Lottery name</th>
          <th scope="col">User numbers</th>
          <th scope="col">Server numbers</th>
          <th scope="col">Winnings</th>
        </tr>
      </thead>
      <tbody>
      </tbody>
    </table>`);

    for (const lottery of lotteries)
    {
      const timestamp = new Date( (+lottery.game_info.started_at) * 1000 ).toISOString(),
            user_no = lottery.enrolled_users[user.profile.username].numbers.join(", "),
            server_no = lottery.numbers.join(", ");

      $("#lottery-table tbody").append(`
      <tr>
        <th scope="row">${timestamp}</th>
        <td>${lottery.lottery_name}</td>
        <td>${user_no}</td>
        <td>${server_no}</td>
        <td>$${lottery.winnings}</td>
      </tr>`);
    }
  },
  on_view_jackpots: function(user) {
    if (user.profile['jackpot'] === undefined)
    {
      return $("#user-information").html(`
      <p class='lead'>No jackpot information exists</p>
        `);
    }
    const jackpots = Object.values(user.profile.jackpot);
    $("#user-information").html(`
    <table class="table table-sm" id="jackpot-table">
      <thead>
        <tr>
          <th scope="col">Timestamp</th>
          <th scope="col">Jackpot name</th>
          <th scope="col">Bet</th>
          <th scope="col">Player count</th>
          <th scope="col">Winnings</th>
          <th scope="col">Winner</th>
        </tr>
      </thead>
      <tbody>
      </tbody>
    </table>`);
    for (const jackpot of jackpots)
    {
      const player_count = Object.keys(jackpot.enrolled_users).length,
            bet = jackpot.enrolled_users[user.profile.username],
            timestamp = new Date( (+jackpot.started_at) * 1000).toISOString(),
            winnings = (jackpot.winner == user.profile.username)? jackpot.jackpot: 0;
      $("#jackpot-table tbody").append(`
      <tr>
        <th scope="row">${timestamp}</th>
        <td>${jackpot.jackpot_name}</td>
        <td>$${bet}</td>
        <td>${player_count}</td>
        <td>$${( (winnings * 100) << 0) / 100}</td>
        <td>${jackpot.winner}</td>
      </tr>`);
    }
  },
  on_user_toggle_disable: function(user) {
    post_message({
      action: "toggle_user_disable",
      username: user.profile.username
    });
    $("#disable").html(`<u>${(!user.profile.disabled)? "Undisable": "Disable"}</u>`);
    return $("#user-information").html(`
    <p class='lead'>${ (!user.profile.disabled)? "Disabled": "Undisabled"} the user successfully</p>
      `);
  }
});

function on_userlist_retrieve(users)
{
  $("#user-list").empty();
  for (const user of users)
  {
    $("#user-list").append($(`<div class='border-bottom p-2'>`).html(
      $("<small class='ml-2'>").text(user['username'])
    ).click(function() {
      if (currently_active_user == $(this))
        { return; }
      else if (currently_active_user !== null)
        { currently_active_user.removeClass("user-selected"); }

      currently_active_user = $(this).addClass("user-selected");
      notify("info", `Username: ${user['username']}`);
      notify("info", `Lottery points: ${user['lottery']['points']}`);
      notify("info", `Email: ${user['email']}`);
      notify("info", `XP: ${user['xp']}`);
      const is_disabled = user['disabled'] === undefined? false: user['disabled'];
      $("#main-container").html(`
      <div class="d-flex flex-column flex-grow-1">
        <div class="border-bottom">
          <h3 class="p-3 ml-3">${user.username}</h3>
        </div>
        <div class="d-flex flex-grow-1">
          <div class="d-flex flex-column border-right" id="user-options">
            <span class="p-2 user-action user-action-active"
              name="view-profile"><u>Profile info</u></span>
            <span class="p-2 user-action"
              name="view-withdrawals"><u>View withdrawals</u></span>
            <span class="p-2 user-action"
              name="view-deposits""><u>View deposits</u></span>
            <span class="p-2 user-action"
              name="view-lotteries"><u>Lottery history</u></span>
            <span class="p-2 user-action"
              name="view-jackpots"><u>Jackpot history</u></span>
            <span class="p-2 user-action" id="disable"
              name="disable"><u>${is_disabled? "Undisable": "Disable"}</u></span>
          </div>
          <div class="d-flex flex-column flex-grow-1 m-3" id="user-information">
            <small class='text-muted'>loading user information...</small>
          </div>
        </div>
      </div>
        `);
      $("#user-options span").each(function(_, action) {
        action = $(action);
        if (action.hasClass("user-action-active"))
        {
          currently_active_action = action;
        }
        action.click(function() {
          if (currently_active_action == action && action.attr("name") !== "disable") { return; }
          $("#user-information").html($("<small class='text-muted'>").text("loading user information..."));
          reset_active_state();
          currently_active_action.removeClass("user-action-active");
          currently_active_action = action;
          action.addClass("user-action-active");
          return post_message({
            action: "load_action",
            username: user['username'],
            name: action.attr("name"),
          });
        });
      });
      return post_message({
        action: "load_action",
        username: user.username,
        name: "view-profile"
      });
    }));
  }
}

function event_main()
{
  $("#content-container").html(`
  <div class="d-flex flex-grow-1">
    <div id="user-list-container" class="d-flex flex-column pt-3 border-right">
      <span class="text-center pb-2 border-bottom">User-list</span>
      <div id="user-list" class="d-flex flex-column">
        <small class='text-muted text-center mt-3'>loading users...</small>
      </div>
    </div>
    
    <div id="main-container" class="flex-grow-1 p-3 pl-0">
      <span class="m-3">
        Select any user from the left hand-side to view their information
        or administrate
      </span>
    </div>
  </div>
    `);
  window.EVENT_CALLBACKS['load_userlist'] = on_userlist_retrieve;
  return post_message({
    action: "load_userlist"
  });
}
