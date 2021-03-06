if ($$username && !$("a#nav-username").get().length) {
  $(".navbar-nav.mr-auto").append(
    $("<li></li>").addClass("nav-item").append(
      $("<a></a>").addClass("nav-link").text($$username).attr({
        id: "nav-username",
        href: "#",
        name: "profile/" + $$username
      })
    )
  ).append(
    $("<li></li>").addClass("nav-item").append(
      $("<a></a>").addClass("nav-link").text("wallet").attr({
        id: "nav-wallet",
        href: "#",
        name: "wallet"
      })
    )
  ).append(
    $("<li></li>").addClass("nav-item").append(
      $("<a></a>").addClass("nav-link").text("provably fair").attr({
        id: "nav-provably-fair",
        href: "#",
        name: "provably_fair"
      })
    )
  ).append(
    $("<li></li>").addClass("nav-item").append(
      $("<a></a>").addClass("nav-link").text("logout").attr({
        id: "nav-logout",
        href: "#",
        name: "logout"
      })
    )
  );
  $("#nav-login").parent().hide();
  $("#nav-register").parent().hide();
  $("#title").text("Pots Bet (" + $$username + ")");
} else if (!$$username && (nav = $("a#nav-username")).get().length) {
  nav.parent().remove();
  $("#nav-logout").parent().remove();
  $("#nav-wallet").parent().remove();
  $("#nav-provably-fair").parent().remove();

  $("#nav-login").parent().show();
  $("#nav-register").parent().show();
  display_notif("logged out", "info");
}
