var TYPES = {
  error: "rgba(220, 53, 69, 0.5)",
  info: "rgba(23, 162, 184, 0.5)",
  success: "rgba(40, 167, 69, 0.5)",
  warning: "rgba(253, 126, 20, 0.5)"
}

var last_ping = +new Date;
var username_profile = null;
window.lottery_intervals = {};

function create_prng(seed) {
  return function() {
    x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
  }
}

function prng_randint(ng, start, end)
{
  return Math.round((end - start) * ng() + start);
}

function prng_choice(ng, seq)
{
  return seq[prng_randint(ng, 0, seq.length - 1)];
}

function is_mobile() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

String.prototype.toProperCase = function () {
    return this.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
};

function reset_state() {
  if (window.in_chatbox !== undefined && window.in_chatbox) {
    $("#main_container").removeClass("d-none");
    if (is_mobile()) {
      $("#chatbox").removeClass("d-flex").addClass("d-none");
    } else {
      $("#chatbox").css({width: "27%"});
    }
  }
}

window.reset_state = reset_state;

function on_profile(resp) {
  reset_state();
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
function display_notif(message, type) {
  $("#error_div").append(
    $("<p></p>").text(message).prepend(
      $("<img width='16' height='16'></img>").attr(
        'src', "html/img/caret-down-fill.svg"
      ).click(function() {
        $(this).parent().fadeOut(1000, function() {
          this.remove();
        })
      }).on("load", function() {
        setTimeout(function(elem) {
          elem.parent().fadeOut(1000, function() {
            this.remove()
          });
        }, 2000, $(this));
      })
    ).css({
      borderLeft: "4px solid " + TYPES[type]
    })
  );
}

window.display_notif = display_notif;

var last_clicked_user = null;

function display_user_info(user_info) {
  $("#user-info-container").removeClass("d-none");
  $("#user-info").empty().append(
    $("<label>").text("Username: " + user_info.username),
    $("<label>").text("XP: " + user_info.xp_count + ", "
                    + "Level: " + user_info.level),
    $("<a class='link-primary'>").text("View profile").click(function() {
      username_profile = user_info.username;
      window.ws.send(JSON.stringify({
        action: "profile_info",
        username: user_info.username
      }));
    }).css({
        "text-align": "center"
      })
  );
}

function add_message(message_obj) {
  var prev_msg = $(".message-content")[0];
  var label_obj = $("<label></label>").addClass("message-content");
  $("#chatbox-messages").prepend(
    $("<div></div>").addClass("chatbox-message").append(
      label_obj.text(
        message_obj.username?
          (message_obj.username + ": " + message_obj.content):
          (message_obj.content)
      )
    ).css(message_obj.properties === undefined? {}: message_obj.properties)
     .click(function() {
       if (!message_obj.username)
       {
         return;
       } else if (last_clicked_user === message_obj.username)
       {
         $("#user-info-container").addClass("d-none");
         last_clicked_user = null;
       } else
       {
         last_clicked_user = message_obj.username;
         display_user_info(message_obj);
       }
     })
  );
  if (prev_msg !== undefined && prev_msg.textContent.startsWith(message_obj.username + ":")) {
    label_obj.parent().addClass("border-0");
  }
}

function on_userlist_update(userlist) {
  $("#user-list").empty();
  if (!userlist['userlist'].length)
  {
    $("#user-list").append($("<li class='list-group-item'>").text("no users registered"));
    return;
  }
  for (const user of userlist['userlist'])
  {
    time_since = "offline";
    if (userlist['last_pinged'][user] !== undefined)
    {
      secs_ago = ( ( (+new Date/1000 - userlist['last_pinged'][user])*10 ) >> 0 ) / 10;
      if (secs_ago < 1)
      {
        time_since = "online";
      } else
      {
        time_since = "last available " + secs_ago.toString() + "s ago";
      }
    }
    $("#user-list").append($("<li class='list-group-item'>").text(
      user
    ).click(function() {
      console.log(last_clicked_user, user);
      if (last_clicked_user == user)
      {
        $("#user-info-container").addClass("d-none");
        last_clicked_user = null;
      } else {
        last_clicked_user = user;
        display_user_info(userlist['userdata'][user]);
      }
    }).append($("<span class='form-text'>").text(
      time_since
      ).css(
        (time_since == "online")
        ? {"margin-left": ".75rem", "color": "#28a745"}
        : {"margin-left": ".75rem", "color": "#343a4088"}
      )
    ));
  }
}

function handle_ws_message(event) {
  let content = JSON.parse(event.data);
  if (content.error) {
    display_notif(content.error, "error");
  } else if (content.info) {
    display_notif(content.info, "info");
  } else if (content.action === "do_load") {
    jQuery.globalEval(content.data);  /* is this shady? */
  } else if (content.action === "registered") {
    sessionStorage.setItem("token", content.data.token);
    sessionStorage.setItem("username", content.data.username);
    window.ws.send(JSON.stringify({
      action: "event_handler",
      name: "home"
    }));
  } else if (content.action === "login") {
    if (content.data.token === undefined && content.data.username) {
      window.sessionStorage.setItem("username", content.data.username);
    } else {
      window.sessionStorage.setItem("username", content.data.username);
      window.sessionStorage.setItem("token", content.data.token);
    }
    window.ws.send(JSON.stringify({
      action: "event_handler",
      name: "home"
    }));
  } else if (content.action === "on_message") {
    add_message(content.message);
  } else if (content.action === "profile_info") {
    if (typeof on_profile !== "undefined") {
      on_profile(content.data);
    } else {
      on_public_profile(content.data);
    }
  } else if (content.action === "userlist") {
    if (typeof on_userlist_update !== "undefined") {
      on_userlist_update(content);
    }
  } else if (content.action === "load_wallet") {
    if (typeof on_wallet !== "undefined") {
      on_wallet(content.data);
    }
  } else if (content.action === "create_transaction") {
    if (typeof on_transaction_created !== "undefined") {
      on_transaction_created(content.data);
    }
  } else if (content.action === "jackpot_results") {
    if (typeof on_jackpot_finish !== "undefined") {
      on_jackpot_finish(content);
    }
  } else if (content.action === "place_bet") {
    if (typeof on_jackpot_bet !== "undefined") {
      on_jackpot_bet(content);
    }
  } else if (content.action === "check_transaction") {
    if (typeof on_transaction_event !== "undefined") {
      on_transaction_event(content.data);
    }
  } else if (content.action === "load_transactions") { 
    if (typeof on_transactions_loaded !== "undefined") {
      on_transactions_loaded(content.data);
    }
  } else if (content.action === "pong") {
    $("#last-ping").text("last ping: " + ( (+new Date) - last_ping) + "ms");
    last_ping = +new Date;
  } else if (content.action === "load_lotteries") { 
    if (typeof on_lottery_load !== "undefined") {
      on_lottery_load(content.data);
    }
  } else if (content.action === "lottery_heartbeat") { 
    if (typeof on_lottery_update !== "undefined") {
      on_lottery_update(content.data);
    }
  } else if (content.action === "refresh_jackpot") {
    if (typeof on_jackpot_refresh !== "undefined") {
      on_jackpot_refresh(content.data);
    }
  } else if (content.action === "load_history") {
    if (typeof on_history_load !== "undefined") {
      on_history_load(content.data);
    }
  } else if (content.warning) {
    display_notif(content.warning, "warning");
  } else if (content.success) {
    display_notif(content.success, "success");
  }

  $(".nav-link").each(function(idx, elem) {
    $(elem).off("click");
    $(elem).click(function() {
      if (window.ws === undefined) {
        display_notif("wait a moment for the websockets to initialize", "error");
        return;
      }
      if (this.name === "logout") {
        window.ws.send(JSON.stringify({
          action: "logout"
        }))
      } else {
        window.ws.send(JSON.stringify({
          action: "event_handler",
          name: $(this).attr('name'),
        }));
      }
      $(".nav-link.active").toggleClass("active");
      $(this).toggleClass("active");
    });
  });
}

$(window).on("load", function() {
  if (window.WebSocket === undefined) {
    window.location.href = "unsupported?code=400";
    return;
  }
  window.ws = new WebSocket("wss://" + window.location.host + "/ws-gambling");
  window.ws.onerror = function() {
    display_notif("failed to connect to server websocket feed.", "error");
  }

  window.ws.onopen = function() {
    var token = window.sessionStorage['token'];
    if (token) {
      grecaptcha.ready(function () {
        grecaptcha.execute('6LclcyUbAAAAALvjjxT5jPnnm4AXDYcJzeI6ZrNS', {action: 'submit'}).then(function(tok) {
          ws.send(JSON.stringify({
            action: "verify_recaptcha",
            token: tok
          }));
          setTimeout(function() {
            ws.send(JSON.stringify({
              action: "login",
              token: token
            }));
          }, 1000);
        });
      });
    }
    ws.send(JSON.stringify({
      action: "event_handler",
      name: "home"
    }));
    if (!is_mobile()) {
      $("#nav-chatbox").parent().remove();
      $("#chatbox").removeClass("d-none").addClass("d-flex");
      ws.send(JSON.stringify({
        action: "initialize_chat"
      }));
/*      add_message({
        "content": "welcome to pots.bet, you can talk with others " +
                   "here. please refrain from any profanity, treat" +
                   " others with respect, and have fun.",
        "properties": {
          "font-weight": "600",
          "border": "2px solid #dee2e6",
          "padding": ".75rem",
          "margin-bottom": "auto"
          }
        }); */
    }
    window.nav_update = setInterval(function() {
      ws.send(JSON.stringify({
        action: "event_handler",
        name: "navigation"
      }))
    }, 2500);
    ws.send(JSON.stringify({
      action: "userlist_update"
    }));
    window.userlist_update = setInterval(function() {
      ws.send(JSON.stringify({
        action: "userlist_update"
      }));
      ws.send(JSON.stringify({
        action: "ping"
      }));
    }, 5000);

  }

  window.ws.onmessage = handle_ws_message;
  window.ws.onclose = function(event) {
    if (event.wasClean) {
      display_notif("closed websocket peacefully", "info");
    } else {
      display_notif("closed websocket abruptly", "error");
    }
    if (window.check_confirmation !== undefined)
    {
      for (const tx_id in window.check_confirmation)
      {
        clearInterval(window.check_confirmation(tx_id));
      }
    }
    if (window.lottery_intervals.length > 0)
    {
      for (const lottery in window.lottery_intervals)
      {
        clearInterval(window.lottery_intervals[lottery]);
      }
    }
    clearInterval(window.nav_update);
    clearInterval(window.userlist_update);
    display_retry_dialog(event.wasClean);
  }
});

function display_retry_dialog(was_clean)
{
  $("#main_container").empty().append($("<p class='m-3'>").text(
    was_clean? "The server has shut down temporarily for maintenance"
             : "The server encountered an internal error"
  ));
}

$("#chatbox-input").on("keypress", function(e) {
  var msg;
  if (e.which == 13) {
    $(this).attr("disabled", "disabled");
    if (!(msg = $(this).val())) {
      display_notif("message cannot be empty", "warning");
      setTimeout(function(obj) {
        obj.removeAttr("disabled");
      }, 500, $(this));
      return;
    }
    window.ws.send(JSON.stringify({
      action: "send_message",
      message: msg
    }));
    $(this).val("");
    setTimeout(function(obj) {
      obj.removeAttr("disabled");
      $("#chatbox-input:text:visible:first").focus()
    }, 250, $(this));
  }
});
