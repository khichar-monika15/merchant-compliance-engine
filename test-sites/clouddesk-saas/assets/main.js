// CloudDesk — minimal UI interactions
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.btn, .btn-secondary').forEach(function (btn) {
    if (btn.href === '#' || !btn.href) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
      });
    }
  });
});
