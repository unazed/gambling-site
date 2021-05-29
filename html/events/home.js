reset_state();
$("#main_container").empty();
$("#main_container").append(`
  <p class="p-2 text-justify">
    Welcome to the <b>Gambling Site</b>
  </p>
  <ul class="service-item list-group list-group-flush">
    <li class="list-group-item bg-transparent">
      <a class="list-group-item-action" name="sample_event_1">Example action 1</a>
    </li>
    <li class="service-item list-group-item bg-transparent">
      <a class="list-group-item-action" name="sample_event_2">Example action 2</a>
    </li>
    <li class="service-item list-group-item bg-transparent">
      <a class="list-group-item-action" name="sample_event_3">Example action 3</a>
    </li>
  </ul>`);

$(".service-item a").each(function(idx, elem) {
  $(elem).click(function() {
    window.ws.send(JSON.stringify({
      action: "event_handler",
      name: elem.name.toLowerCase()
    }));
  });
});
