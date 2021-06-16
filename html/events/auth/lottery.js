reset_state();

function on_lottery_load(lotteries)
{
  $("#lottery-container").empty();
  console.log(lotteries);
  for (const lottery of lotteries.list) {
    $("#lottery-container").append(
      $("<div class='d-flex p-2'>").append(
        $("<div class='border p-3'>").append(
          $("<small>").text(lottery['name']).css({
            "font-size": "16px",
            "text-transform": "uppercase"
          })
        ).css({
          "height": "fit-content",
          "max-width": "9em",
          "overflow-x": "scroll"
        }),
        $("<div>").append(
          $("<div class='border p-3'>").append(
            $("<small>").text("entry: $" + lottery.entry_requirements.usd_price),
            $("<small class='ml-3'>").text("minimum level: " + lottery.entry_requirements.min_level),
            $("<small class='ml-3'>").text("max tickets: " + lottery.max_tickets),
            (!is_mobile())? 
              $("<small class='pl-3 ml-3'>").text(lotteries.active[lottery['name']].is_active? "currently in procession": "available to join")
                .css({"border-left": "1px solid hsla(210, 14%, 74%, 1)"})
            :  $("<small class='border-left pl-3 ml-3'>").text(lotteries.active[lottery['name']].is_active? "busy": "free")
          ),
          $("<div class='border border-top-0 p-2'>").append(`
          <div class="input-group">
            <div class="input-group-prepend">
              <span class="input-group-text" id="quantity" style="
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
              ">Qty.</span>
            </div>
            <input type="number" min="1" max="` + lottery.max_tickets + `" step="1" class="form-control ` + ( is_mobile()? "quantity-mobile": "" ) + `"
              aria-label="Quantity" aria-describedby="quantity" id="` + lottery['name'] + "-quantity" + `">
            <div class="input-group-append">
              <button class="btn enter-btn btn-outline-primary" type="button" style="
                border-bottom-left-radius: 0;
                border-top-left-radius: 0;
                " ` + ( lotteries.active[lottery['name']].is_active? "disabled": "" ) + ` id="` + lottery['name'] + "-btn" + `">Enter</button>
            </div>
          </div>
          `).css({
            "position": "absolute",
            "right": is_mobile()? "0": "3em",
            "background-color": "hsla(204, 16%, 97%, 1)",
          })
        ).css({
          "flex-grow": "1",
          "height": "fit-content",
          "position": "relative",
          "background-color": "hsla(210, 17%, 94%, 1)"
        })
      ).addClass(is_mobile()? "lottery-item-mobile": "lottery-item")
    );
    button = $("#" + lottery['name'].replace(" ", "\\ ") + "-btn");
    button.click(function() {
      quantity = $("#" + lottery['name'].replace(" ", "\\ ") + "-quantity");
      button.prop("disabled", true);
      window.ws.send(JSON.stringify({
        action: "enter_lottery",
        quantity: quantity.val()
      }));
    });
  }
}

$("#main_container").empty().append(
  $("<p class='lead m-3 mb-0'>").text("Participate in multi-tier lotteries; win incrementally larger prizes. Take a shot at our provably fair lottery and win large."),
  $("<div id='lottery-container' class='mt-3 p-2 mb-3'>").append(
    $("<small class='text-muted'>").text("loading lotteries...")
  ),
);

window.ws.send(JSON.stringify({
  action: "load_lotteries"
}));
