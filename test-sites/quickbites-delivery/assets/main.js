// QuickBites — main.js
document.querySelectorAll('.btn').forEach(function(btn) {
  btn.addEventListener('click', function(e) {
    if (this.textContent === 'Order Now') {
      e.preventDefault();
    }
  });
});
