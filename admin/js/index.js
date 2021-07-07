const NOTIFICATION_COLORMAP = {
  "info": ["orange", "hsl(39deg 94% 50% / 20%)"],
  "success": ["green", "hsl(120deg 94% 31% / 20%)"],
  "error": ["red", "hsl(354deg 50% 54% / 20%)"]
  };

const ACTION = {
    identify: function(data) {
      notify("success", `Successfully identified, IP: ${data.ip_address}`);
      return post_message({
        action: "load",
        name: "login"
      });
    },
    notify: function(data) {
      return notify(data['type'], data['reason']);
    },
    load: function(data) {
      jQuery.globalEval(data.data);
      return event_main();
    }
  };

var EVENT_CALLBACKS = {};

function notify(type, message)
{
  var notif = $(`<div class='border-bottom pl-3 pr-3'>
                   <span>${message}</span>
                 </div>`).css({
                   "border-left": `.5em solid ${NOTIFICATION_COLORMAP[type][0]}`,
                   "background-color": NOTIFICATION_COLORMAP[type][1]
                  });
  $("#notifications").append(notif);  
}

function post_message(data)
{
  if (typeof window.feed !== "undefined")
  {
    return window.feed.send(JSON.stringify(data));
  }
}

function handle_feed_message(data)
{
  return ACTION[data['action']](data);
}

$(window).on("load", function() {
  if (window.WebSocket === undefined)
  {
    return notify("error", "Your browser doesn't support websockets");
  }

  window.feed = new WebSocket("wss://" + window.location.host + "/ws-admin");

  window.feed.onerror = function() {
    return notify("error", "Failed to connect to websocket feed to websocket feed");
  }

  window.feed.onopen = function() {
    notify("success", "Established websocket connection with server");
    post_message({action: "identify"});
  }

  window.feed.onmessage = function(e) {
    return handle_feed_message(JSON.parse(e.data));
  }
});
