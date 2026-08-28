// Artisan Weaves — main.js
let cart = [];

document.querySelectorAll('.product-card .btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var card = this.closest('.product-card');
    var name = card.querySelector('h3').textContent;
    var price = card.querySelector('.price').textContent;
    cart.push({ name: name, price: price });
    this.textContent = 'Added!';
    setTimeout(function(b) { b.textContent = 'Add to Cart'; }.bind(null, this), 1500);
  });
});
