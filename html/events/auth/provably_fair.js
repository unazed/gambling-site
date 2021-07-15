reset_state();

function on_history_load(data)
{
  var is_first = true;
  $("#lotteries").empty();
  for (const lottery of data.lotteries)
  {
    const cl_numbers_arr = lottery['enrolled_users'][lottery['from_jackpot']][$$username].numbers,
          sv_numbers_arr = lottery['numbers'],
          cl_seed = lottery['enrolled_users'][lottery['from_jackpot']][$$username].seed;

    const timestamp = (new Date(+lottery['started_at'] * 1000)).toISOString(),
          sv_numbers = lottery.numbers.join(', '),
          cl_numbers = cl_numbers_arr.join(', ');

    $("#lotteries").append(row = $(`
    <div class="d-flex flex-grow-1 border-bottom pb-2 ${is_first? "": "pt-2"}">
      <small class='text-muted'>${timestamp}</small>
      <small class='ml-2'>${lottery['lottery_name']}</small>
      <small class='ml-2'>Server #'s: ${sv_numbers}</small>
    </div>
      `));
    row.click(function() {
      $("#input").html( verify_form = $(`
      <small>Server seed: ${lottery['server_seed']}</small>
      <small class="border-left pl-2 ml-2">Your seed: ${cl_seed}</small>
      <button type="button" class="ml-auto btn btn-outline-primary" id="lottery-verify-btn">Verify lottery results</button>
        `) );
      $("#verifier").removeClass("d-none").addClass("d-flex");
      $("#output").empty();
      $("#output-server").empty();
      $("#lottery-verify-btn").click(function() {
        const sv_prng = create_prng(lottery['server_seed']),
              cv_prng = create_prng(cl_seed);
        $("#output").html(`<p>Client rolls</p>`);
        $("#output-server").html(`<p>Server rolls</p>`);
        for (idx = 0; idx < cl_numbers_arr.length; ++idx)
        {
          generated_number = prng_randint(cv_prng, 1, 100);
          expected_number = cl_numbers_arr[idx];
          $("#output").append($("<small>").text(`generated: ${generated_number}, expected: ${expected_number}... ${(generated_number == expected_number)? "good": "bad"}`).addClass("text-muted"));
        }
        for (const expected_number of sv_numbers_arr)
        {
          generated_number = prng_randint(sv_prng, 1, 100);
          $("#output-server").append($("<small>").text(`generated: ${generated_number}, expected: ${expected_number}... ${(generated_number == expected_number)? "good": "bad"}`).addClass("text-muted"));
        }
      });
    });
    is_first = false;
  }
  if (!data.lotteries.length)
  {
    $("#lotteries").html(`
    <small class='text-muted'>you have no lottery history</small>
      `);
  }

  is_first = true;

  $("#jackpots").empty();
  for (const jackpot of data.jackpots)
  {
    const timestamp = (new Date(+jackpot['started_at'] * 1000)).toISOString(),
          winner = jackpot.winner;
    $("#jackpots").append($(`
    <div class="d-flex flex-grow-1 border-bottom pb-2 ${is_first? "": "pt-2"}">
      <small class='text-muted'>${timestamp}</small>
      <small class='ml-2'>${jackpot['jackpot_name']}</small>
      <small class='ml-2'>Winner: ${winner}</small>
    </div>
      `).click(function() {
        $("#input").html(`
      <small>Server seed: ${jackpot['server_seed']}</small>
      <button type="button" class="ml-auto btn btn-outline-primary" id="jackpot-verify-btn">Verify jackpot results</button>
          `);
        $("#verifier").removeClass("d-none").addClass("d-flex");
        $("#output-server").empty();
        $("#output").empty();
        $("#jackpot-verify-btn").click(function() {
          const sv_prng = create_prng(jackpot.server_seed);
          var enrolled_users = [],
              proportion = [];
          for (const [name, amount] of Object.entries(jackpot['enrolled_users'])) { enrolled_users.push([name, amount]); }
          enrolled_users.sort();
          for (const arr of enrolled_users)
          {
            /* if amount is None:
                 continue
               proportion.extend([user] * (int(amount) - int(jackpot_templ['min']) + 1)) */
            name = arr[0];
            amount = arr[1];
            if (amount === null) { continue; }
            for (idx = 0; idx < ( (+amount) - (+jackpot.templ.min) +1); ++idx)
            {
              proportion.push(name);
            }
          }
          const winner = prng_choice(sv_prng, proportion);

          $("#output-server").html(`<small class='text-muted'>Generated winner: ${winner}, should be: ${jackpot.winner}</small>`);
        });
      }));
    is_first = false;
  }
  if (!data.jackpots.length)
  {
    $("#jackpots").html(`
    <small class='text-muted'>you have no jackpot history</small>
      `);
  }
}

$("#main_container").html(`
<p class='lead m-3'>Select any row to view event metadata</p>
<div class="d-flex flex-grow-1">
  <div id="lotteries" class="flex-grow-1 d-flex flex-column mr-1 p-2 border ml-2">
    <small class='text-muted'>loading lotteries...</small>
  </div>
  <div id="jackpots" class="flex-grow-1 d-flex flex-column ml-1 p-2 border mr-2">
    <small class='text-muted'>loading jackpots...</small>
  </div>
</div>
<div id="verifier" class="d-none flex-column m-4 mt-3 p-3 border">
  <div id="input" class="d-flex">
  </div>
  <div id="output-container" class="d-flex">
    <div id="output" class="d-flex flex-column ml-2 pl-2 border-left">
    </div>
    <div id="output-server" class="d-flex flex-column ml-2 pl-2 border-left">
    </div>
  </div>
</div>
`);

window.ws.send(JSON.stringify({
  action: "load_history"
}));
