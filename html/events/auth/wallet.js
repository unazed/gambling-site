reset_state();

function on_wallet(wallet_info) {
  console.log(wallet_info);
}

$("#main_container").empty().append(
  $("<div class='container m-3 p-3 border'>").append(
    $("<div id='wallet-container' class='border m-1 p-2'>").append(
      $("<div id='wallet'>").append(
        $("<span>").text("loading wallet...")
      ),
      $("<div id='wallet-action'>").append(
        $("<span>").text("loading wallet actions...")
      )
    ),
    $("<p>").text(`
    You can view and manage your wallet here; at the moment, deposits and withdrawals are only available
    in Bitcoin and/or Ethereum. Note that whatever quantity of cryptocurrency you deposit must be matched
    during your betting, e.g. if you deposited $20/BTC + $10/ETH then you must match your bets to $30
    before being able to withdraw
    `).css({"text-align": "justify"})
  )
);

window.ws.send(JSON.stringify({
  action: "load_wallet",
  markets: ["bitcoin", "ethereum"]
}));
