// FreshKart India — main.js
let cart = JSON.parse(localStorage.getItem('fk_cart') || '[]');

function addToCart(name, price) {
  cart.push({ name, price });
  localStorage.setItem('fk_cart', JSON.stringify(cart));
  const count = cart.length;
  document.title = `(${count}) FreshKart India`;
}

function removeItem(btn) {
  const item = btn.closest('.cart-item');
  if (item) item.remove();
}

function filterCategory(cat) {
  document.querySelectorAll('.product-card').forEach(card => {
    card.style.display = (cat === 'all' || card.dataset.category === cat) ? '' : 'none';
  });
}

function submitForm(e) {
  e.preventDefault();
  alert('Thanks! We will get back to you at hello@freshkart.in');
}
