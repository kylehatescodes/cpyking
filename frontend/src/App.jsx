import OrderEntryForm from './components/OrderEntryForm';

const menuItems = [
  { id: 1, name: 'Crispy Burger', sku: 'MENU-001', price: 8.5 },
  { id: 2, name: 'Classic Fries', sku: 'MENU-002', price: 3.25 },
  { id: 3, name: 'Spicy Wrap', sku: 'MENU-003', price: 7.75 },
  { id: 4, name: 'Soft Drink', sku: 'MENU-004', price: 2.0 },
  { id: 5, name: 'Chicken Combo', sku: 'MENU-005', price: 11.25 },
];

export default function App() {
  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <OrderEntryForm menuItems={menuItems} />
    </main>
  );
}
