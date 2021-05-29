reset_state();

String.prototype.capitalize = function() {
  return this.charAt(0).toUpperCase() + this.slice(1)
}

function on_results(resp) {
  results = $("#results");
  results.empty();
  if (jQuery.isEmptyObject(resp)) {
    results.append(
      $("<li>").addClass("list-group-item bg-transparent").append(
        $("<p>").addClass("p-2").text("No results found, maybe try run a check")
      )
    );
    return;
  }

  /* <div class="dropdown-menu">
      <h6 class="dropdown-header">Dropdown header</h6>
      <a class="dropdown-item" href="#">Action</a>
      <a class="dropdown-item" href="#">Another action</a>
     </div> */

  for (const service in resp) {
    container = $("<div class='dropdown-menu dropdown-custom'>").append($("<h6 class='dropdown-header'>")
             .html(`${service.capitalize()} (${Object.keys(resp[service]).length} checks)`))
              .removeAttr('display position');
    for (const id in resp[service]) {
      result = resp[service][id]['result'];
      started = resp[service][id]['started'];
      if (started < 60) {
        started = `started ${started << 0} second(s) ago`;
      } else {
        started = `started ${(started / 60) << 0} minute(s) and ${(started % 60) << 0} second(s) ago`;
      }
      task = $("<a>").addClass("dropdown-item")
                     .html((result === false)? `task #${id} not completed, ${started}`:
                                               `<b>#${id}</b>: ${started}`);
      if (result !== false) {
        task.attr({'href': result, 'target': '_blank'});
      } else {
        task.addClass('disabled');
      }
      container.append(task);
    }
    results.prepend(container);
  }
}

function on_profile(resp) {
  $("#profile-info").empty().append(
    $("<li>").addClass("list-group-item bg-transparent").append(
      $("<label>").text("Username: " + resp.username)
    ),
    $("<li>").addClass("list-group-item bg-transparent").append(
      $("<label>").text("Currently running checks: " + resp.running_checks)
    ),
    $("<li>").addClass("list-group-item bg-transparent").append(
      $("<label>").text("Overall check count: " + resp.completed_checks)
    ),
    $("<li>").addClass("list-group-item bg-transparent").append(
      $("<label>").text("Rank: " + resp.rank)
              .css({"margin-bottom": "0"})
    ).append($("<ul>").addClass("list-group-flush").append(
      $("<li>").addClass("list-group-item bg-transparent").append(
        $("<label>").text("Maximum usernames: " +
          resp.rank_permissions.max_usernames)
      ),
      $("<li>").addClass("list-group-item bg-transparent").append(
        $("<label>").text("Maximum tasks: " +
          resp.rank_permissions.max_tasks)
      ),
    ).css({"padding-left": ".25em", "border-left": "2px solid rgba(0,0,0,.125)"})),
  ).css({
    "max-height": $("#results").height()
  });
}

window.ws.send(JSON.stringify({
  action: "service_results"
}));

window.ws.send(JSON.stringify({
  action: "profile_info"
}));

$("#main_container").empty().append(
  $("<div>").addClass("d-flex flex-row border").append(
    $("<ul>").addClass("list-group flex-grow").prop("id", "results").append(
      $("<li>").addClass("list-group-item bg-transparent").append(
        $("<p>").addClass("p-2").text("Loading checks")
      )
    ).css({
      "margin": "1em",
      "flex-grow": "1",
      "overflow": "auto",
//      "height": "376px"
    }),
    $("<ul>").addClass("list-group flex-grow").prop("id", "profile-info").append(
      $("<li>").addClass("list-group-item bg-transparent").append(
        $("<p>").addClass("p-2").text("Loading profile")
      )
    ).css({"margin": "1em", "margin-left": "0"})
  )
);
