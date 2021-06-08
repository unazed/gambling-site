reset_state();

var is_confirmed = false;

function on_wallet(wallet_info) {
  console.log(wallet_info);
  deposit_info = wallet_info.deposit;
  withdraw_info = wallet_info.withdraw;
  total_btc_balance = deposit_info['per-market-volume']['btc']
    - withdraw_info['per-market-volume']['btc'];
  total_eth_balance = deposit_info['per-market-volume']['eth']
    - withdraw_info['per-market-volume']['eth'];

  btc_usd = total_btc_balance * wallet_info.market_prices['BTC']['USD']
  eth_usd = total_eth_balance * wallet_info.market_prices['ETH']['USD']

  console.log(total_btc_balance, total_eth_balance);

  $("#wallet").empty().append(`
<div id="wallet-info" class="p-3 border-bottom mb-2">
  <p class='lead'>Balance</p>
</div>

<div id="deposits" class="p-3 border-bottom mb-2">
  <p class='lead'>Deposits</p>
</div>

<div id="withdrawals" class="p-3">
  <p class='lead'>Withdrawals</p>
</div>
`);

  $("#wallet-info").append(
    $("<span>").text("Bitcoin: " + total_btc_balance + ", Ethereum: " + total_eth_balance),
    $("<span>").text("Net: $" + (btc_usd + eth_usd))
  );

  /* TODO: implement loading tx/rx. info */
  if (!deposit_info.transactions.length)
  {
    $("#deposits").append($("<span>").text("No deposit history"));
  }

  if (!withdraw_info.transactions.length)
  {
    $("#withdrawals").append($("<span>").text("No withdrawal history"));
  }

  $("#wallet-action").empty().append(`
<div id="wallet-action-container" class="p-4">
  <div id="wallet-action-form" class="border-bottom pb-3">
    <div class="input-group mb-3">
      <input type="text" id="rx-tx-amount" class="form-control" placeholder="amount to withdraw">
      <span class="input-group-text" id="price-suffix">BTC</span>
    </div>

    <div class="input-group mb-3">
      <input type="text" id="rx-tx-address" class="form-control" placeholder="receiving address">
    </div>

    <div id="mobile-friendly-container">
      <div class="btn-group btn-group-toggle ml-3" data-toggle="buttons">
        <label class="btn btn-outline-primary active">
          <input type="radio" name="options" id="bitcoin-radio" autocomplete="off" checked>
            Bitcoin
        </label>
        <label class="btn btn-outline-primary">
          <input type="radio" name="options" id="ethereum-radio" autocomplete="off">
            Ethereum
        </label>
      </div>

      <div class="btn-group btn-group-toggle pl-3" data-toggle="buttons">
        <label class="btn btn-outline-primary active">
          <input type="radio" name="options" id="withdraw-radio" autocomplete="off" checked>
            Withdraw
        </label>
        <label class="btn btn-outline-primary">
          <input type="radio" name="options" id="deposit-radio" autocomplete="off">
          Deposit
        </label>
      </div>

      <button type="button" class="btn btn-outline-success" id="process-btn">
        Process
      </button>
    </div>
  </div>

  <div id="wallet-action-info" class="ml-2">
    <small>Payments are handled securely, and anonymously. Withdrawals may take up to 24 hours to arrive</small>
    <br>
    <small class='text-muted' id='min-withdraw'>Maximum withdraw $` + wallet_info.cleared + `</small>
  </div>
</div>
  `);

  if (is_mobile())
  {
    $("#wallet-container").removeClass("d-flex");
    $("#wallet-action").addClass("border-top p-3");
    $("#wallet-action-container").removeClass("p-4");
    $("#wallet-ext-container").addClass("mobile-friendly-container");
    $("#mobile-friendly-container").empty().append(`
<div class="btn-group btn-group-toggle ml-3" data-toggle="buttons">
  <label class="btn btn-outline-primary active">
    <input type="radio" name="options" id="bitcoin-radio" autocomplete="off" checked>
      Bitcoin
  </label>
  <label class="btn btn-outline-primary">
    <input type="radio" name="options" id="ethereum-radio" autocomplete="off">
      Ethereum
  </label>
</div>
<br>
<div class="btn-group btn-group-toggle ml-3 mt-2" data-toggle="buttons">
  <label class="btn btn-outline-primary active">
    <input type="radio" name="options" id="withdraw-radio" autocomplete="off" checked>
      Withdraw
  </label>
  <label class="btn btn-outline-primary">
    <input type="radio" name="options" id="deposit-radio" autocomplete="off">
    Deposit
  </label>
</div>
<br>
<button type="button" class="btn btn-outline-success mt-2" id="process-btn">Process</button>
`);
  }  /* is_mobile() */

  is_withdraw_state = true;
  is_bitcoin_state = true;

  $("#ethereum-radio").parent().click(function() {
    if (!is_bitcoin_state) { return; }
    is_bitcoin_state = false;
    $("#price-suffix").text("ETH");
  });

  $("#bitcoin-radio").parent().click(function() {
    if (is_bitcoin_state) { return; }
    is_bitcoin_state = true;
    $("#price-suffix").text("BTC");
  });

  $("#withdraw-radio").parent().click(function() {
    if (is_withdraw_state) { return; }
    is_withdraw_state = true;
    $("#rx-tx-amount").prop("placeholder", "amount to withdraw").text("");
    $("#rx-tx-address").prop("placeholder", "receiving address")
      .prop("disabled", false).text("");
  });

  $("#deposit-radio").parent().click(function() {
    if (!is_withdraw_state) { return; }
    console.log("in deposit state");
    is_withdraw_state = false;
    $("#rx-tx-amount").prop("placeholder", "amount to deposit").val("");
    $("#rx-tx-address").prop("placeholder", "address to which funds must be sent")
      .prop("disabled", true).val("");
  });

  $("#process-btn").click(function() {
    address = $("#rx-tx-address").val();
    amount = $("#rx-tx-amount").val();

    if (!address && is_withdraw_state)
    {
      $("#rx-tx-address").addClass("is-invalid");
      return;
    } else if (!amount)
    {
      $("#rx-tx-amount").addClass("is-invalid");
      return;
    }

    if (is_withdraw_state)
    {
      if (!is_confirmed)
      {
        display_notif("double check your receiving address, and process when you're certain it's the right address", "info");
        $("#process-btn").prop("disabled", true);
        setTimeout(function(){ $("#process-btn").prop("disabled", false); }, 1000);
        is_confirmed = true;
        return;
      }
      $("#process-btn").prop("disabled", true);
      window.ws.send(JSON.stringify({
        action: "create_transaction",
        type: "withdrawal",
        currency: is_bitcoin_state? "bitcoin": "ethereum",
        receive_address: address,
        amount: amount
      }));
      display_notif("withdrawal request has been submitted, waiting for server confirmation...", "success")
    } else /* deposit state */
    {
      window.ws.send(JSON.stringify({
        action: "create_transaction",
        type: "deposit",
        currency: is_bitcoin_state? "bitcoin": "ethereum",
        receive_address: address,
        amount: amount
      }));
      display_notif("deposit request has been submitted, waiting for server confirmation...", "success")
    }
  });
}

$("#main_container").empty().append(
  $("<div id='wallet-ext-container' class='container m-3 p-3 border'>").append(
    $("<div id='wallet-container' class='m-1 mb-3 p-2 d-flex'>").append(
      $("<div id='wallet' class='border-right'>").append(
        $("<span>").text("loading wallet...")
      ),
      $("<div id='wallet-action'>").append(
        $("<span>").text("loading wallet actions...")
      )
    ),
    $("<small class='text-muted'>").text(`
    You can view and manage your wallet here; at the moment, deposits and withdrawals are only available
    in Bitcoin and/or Ethereum. Note that whatever quantity of cryptocurrency you deposit must be matched
    during your betting, e.g. if you deposited $20/BTC + $10/ETH then you must match your bets to $30
    before being able to withdraw
    `).css({"text-align": "justify", "position": "absolute", "bottom": "1em", "left": "1em", "right": "1em"})
  )
);

window.ws.send(JSON.stringify({
  action: "load_wallet",
  markets: ["btc", "eth"]
}));
