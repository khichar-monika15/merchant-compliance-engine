// QuickBites — minimal UI interactions
document.addEventListener('DOMContentLoaded', function () {
  const orderBtn = document.querySelector('.btn');
  if (orderBtn) {
    orderBtn.addEventListener('click', function (e) {
      e.preventDefault();
      alert('Ordering feature coming soon!');
    });
  }
});
