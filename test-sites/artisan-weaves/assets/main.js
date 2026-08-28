// Artisan Weaves — cart and checkout interactions
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.product-card button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const name = btn.closest('.product-card').querySelector('h3').textContent;
      console.log('Added to cart:', name);
      btn.textContent = 'Added!';
      setTimeout(function () { btn.textContent = 'Add to Cart'; }, 1500);
    });
  });
});
