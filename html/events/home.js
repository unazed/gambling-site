reset_state();
$("#main_container").empty();
$("#main_container").append(`
  <p class="p-2 text-justify">
    Welcome to <b>Pots.Bet</b>
  </p>
  <ul class="service-item list-group list-group-flush">
    <li class="list-group-item bg-transparent">
      <a class="list-group-item-action" name="view_lottery">Join the lottery</a>
    </li>
    <li class="service-item list-group-item bg-transparent">
      <a class="list-group-item-action" name="view_jackpot">Gamble in a jackpot against others</a>
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
