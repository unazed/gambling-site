reset_state();

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
<div id="wallet-action-container">
  <div id="wallet-action-form">
  </div>
  <div id="wallet-action-info">
  </div>
</div>
  `);
}

$("#main_container").empty().append(
  $("<div class='container m-3 p-3 border'>").append(
    $("<div id='wallet-container' class='border m-1 mb-3 p-2'>").append(
      $("<div id='wallet' class='border-right'>").append(
        $("<span>").text("loading wallet...")
      ),
      $("<div id='wallet-action'>").append(
        $("<span>").text("loading wallet actions...")
      )
    ),
    $("<small>").text(`
    You can view and manage your wallet here; at the moment, deposits and withdrawals are only available
    in Bitcoin and/or Ethereum. Note that whatever quantity of cryptocurrency you deposit must be matched
    during your betting, e.g. if you deposited $20/BTC + $10/ETH then you must match your bets to $30
    before being able to withdraw
    `).css({"text-align": "justify"})
  )
);

window.ws.send(JSON.stringify({
  action: "load_wallet",
  markets: ["btc", "eth"]
}));
