import { useMemo, useState } from 'react';
import api from '../services/api';

function formatStockError(data) {
  if (!data) {
    return 'Unable to submit order.';
  }

  if (typeof data === 'string') {
    return data;
  }

  const detail = typeof data.detail === 'string' ? data.detail : 'Unable to submit order.';
  const shortages = data.shortages && typeof data.shortages === 'object' ? data.shortages : null;

  if (!shortages) {
    return detail;
  }

  const shortageLines = Object.entries(shortages).map(([name, quantity]) => `${name}: ${quantity}`);
  return shortageLines.length > 0 ? `${detail}\n${shortageLines.join('\n')}` : detail;
}

const fallbackMenuItems = [
  { id: 1, name: 'Crispy Burger', sku: 'MENU-001', price: 8.5 },
  { id: 2, name: 'Classic Fries', sku: 'MENU-002', price: 3.25 },
  { id: 3, name: 'Spicy Wrap', sku: 'MENU-003', price: 7.75 },
  { id: 4, name: 'Soft Drink', sku: 'MENU-004', price: 2.0 },
];

export default function OrderEntryForm({ menuItems = fallbackMenuItems }) {
  const [customer, setCustomer] = useState({ name: '', phone: '', email: '' });
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMenuItem, setSelectedMenuItem] = useState(menuItems[0] || null);
  const [quantity, setQuantity] = useState('1');
  const [orderItems, setOrderItems] = useState([]);
  const [statusMessage, setStatusMessage] = useState('Ready to build an order.');
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filteredMenuItems = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return menuItems;
    }

    return menuItems.filter((item) => {
      const name = (item.name || '').toLowerCase();
      const sku = (item.sku || '').toLowerCase();
      return name.includes(query) || sku.includes(query);
    });
  }, [menuItems, searchTerm]);

  function updateCustomerField(field, value) {
    setCustomer((current) => ({ ...current, [field]: value }));
  }

  function handleSelectMenuItem(item) {
    setSelectedMenuItem(item);
    setSearchTerm(item.name || '');
  }

  function handleAddSelectedItem() {
    if (!selectedMenuItem) {
      setErrorMessage('Please choose a menu item before adding it to the order.');
      return;
    }

    const parsedQuantity = Number.parseInt(quantity, 10);
    if (!Number.isInteger(parsedQuantity) || parsedQuantity <= 0) {
      setErrorMessage('Quantity must be a positive integer.');
      return;
    }

    setErrorMessage('');
    setOrderItems((currentItems) => {
      const existingIndex = currentItems.findIndex((item) => item.product_id === selectedMenuItem.id);
      if (existingIndex >= 0) {
        return currentItems.map((item, index) => {
          if (index !== existingIndex) {
            return item;
          }

          return {
            ...item,
            quantity: item.quantity + parsedQuantity,
          };
        });
      }

      return [
        ...currentItems,
        {
          product_id: selectedMenuItem.id,
          name: selectedMenuItem.name,
          sku: selectedMenuItem.sku,
          quantity: parsedQuantity,
        },
      ];
    });
  }

  function updateOrderQuantity(productId, nextQuantity) {
    const parsedQuantity = Number.parseInt(nextQuantity, 10);
    if (!Number.isInteger(parsedQuantity) || parsedQuantity <= 0) {
      return;
    }

    setOrderItems((currentItems) =>
      currentItems.map((item) =>
        item.product_id === productId
          ? {
              ...item,
              quantity: parsedQuantity,
            }
          : item,
      ),
    );
  }

  function removeOrderItem(productId) {
    setOrderItems((currentItems) => currentItems.filter((item) => item.product_id !== productId));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage('');

    if (orderItems.length === 0) {
      setErrorMessage('Add at least one menu item before submitting the order.');
      return;
    }

    const orderPayload = {
      customer,
      products: orderItems.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
      })),
    };

    try {
      setIsSubmitting(true);
      setStatusMessage('Submitting order...');
      const response = await api.post('/orders/', orderPayload);

      if (response.status === 201) {
        window.alert(`Order submitted successfully. Order #${response.data.order_number}`);
        setCustomer({ name: '', phone: '', email: '' });
        setSearchTerm('');
        setSelectedMenuItem(menuItems[0] || null);
        setQuantity('1');
        setOrderItems([]);
        setStatusMessage(`Order created successfully as #${response.data.order_number}.`);
      }
    } catch (error) {
      const responseStatus = error?.response?.status;
      if (responseStatus === 400) {
        setErrorMessage(formatStockError(error.response.data));
      } else {
        setErrorMessage(error?.response?.data?.detail || 'Unable to submit order.');
      }
      setStatusMessage('Order submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const orderTotal = orderItems.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <div className="mx-auto w-full max-w-6xl rounded-3xl border border-white/10 bg-slate-950/80 p-6 shadow-2xl shadow-black/30 backdrop-blur md:p-8">
      <div className="flex flex-col gap-2 border-b border-white/10 pb-6">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-brand-200">Crispy King</p>
        <h1 className="text-3xl font-semibold text-white sm:text-4xl">Order Entry Form</h1>
        <p className="max-w-3xl text-sm leading-6 text-slate-400">
          Search menu items, build the order list, and submit the compiled payload to the Django backend.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-8 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-200">Customer Name</span>
              <input
                type="text"
                value={customer.name}
                onChange={(event) => updateCustomerField('name', event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-brand-400"
                placeholder="Enter customer name"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-200">Phone</span>
              <input
                type="tel"
                value={customer.phone}
                onChange={(event) => updateCustomerField('phone', event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-brand-400"
                placeholder="555-0100"
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="mb-2 block text-sm font-medium text-slate-200">Email</span>
              <input
                type="email"
                value={customer.email}
                onChange={(event) => updateCustomerField('email', event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-brand-400"
                placeholder="customer@example.com"
              />
            </label>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <div className="grid gap-4 md:grid-cols-[1fr_180px] md:items-end">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-200">Search menu items</span>
                <input
                  type="search"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-brand-400"
                  placeholder="Search by name or SKU"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-200">Quantity</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-brand-400"
                  placeholder="1"
                />
              </label>
            </div>

            <div className="mt-5 grid gap-3">
              {filteredMenuItems.length > 0 ? (
                filteredMenuItems.map((item) => {
                  const isSelected = selectedMenuItem?.id === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleSelectMenuItem(item)}
                      className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                        isSelected
                          ? 'border-brand-400 bg-brand-500/15 text-white'
                          : 'border-white/10 bg-slate-950/60 text-slate-200 hover:border-white/20 hover:bg-white/5'
                      }`}
                    >
                      <div>
                        <p className="font-medium">{item.name}</p>
                        <p className="text-sm text-slate-400">SKU: {item.sku}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-medium text-brand-100">${Number(item.price || 0).toFixed(2)}</p>
                        {isSelected ? <p className="text-xs text-brand-100">Selected</p> : null}
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-2xl border border-dashed border-white/15 px-4 py-6 text-sm text-slate-400">
                  No menu items match your search.
                </div>
              )}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleAddSelectedItem}
                className="rounded-2xl bg-brand-500 px-5 py-3 font-medium text-white transition hover:bg-brand-600"
              >
                Add Item
              </button>
              {selectedMenuItem ? (
                <span className="rounded-full bg-white/10 px-4 py-2 text-sm text-slate-200">
                  Selected: {selectedMenuItem.name}
                </span>
              ) : null}
            </div>
          </div>
        </section>

        <aside className="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
          <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
            <div>
              <h2 className="text-xl font-semibold text-white">Order Items</h2>
              <p className="text-sm text-slate-400">Total items: {orderTotal}</p>
            </div>
            <span className="rounded-full bg-brand-500/15 px-4 py-2 text-sm font-medium text-brand-100">
              {orderItems.length} line(s)
            </span>
          </div>

          <div className="mt-4 space-y-3">
            {orderItems.length > 0 ? (
              orderItems.map((item) => (
                <div key={item.product_id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium text-white">{item.name}</p>
                      <p className="text-sm text-slate-400">SKU: {item.sku}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeOrderItem(item.product_id)}
                      className="text-sm font-medium text-rose-300 transition hover:text-rose-200"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="mt-4 flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-slate-300">
                      Quantity
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={item.quantity}
                        onChange={(event) => updateOrderQuantity(item.product_id, event.target.value)}
                        className="w-24 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none focus:border-brand-400"
                      />
                    </label>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-white/15 p-6 text-sm text-slate-400">
                No order items added yet.
              </div>
            )}
          </div>

          <div className="mt-6 space-y-3 rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm">
            <p className="font-medium text-white">Submission Status</p>
            <p className="text-slate-300">{statusMessage}</p>
            {errorMessage ? <p className="whitespace-pre-line text-rose-300">{errorMessage}</p> : null}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-5 w-full rounded-2xl bg-white px-5 py-3 font-semibold text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:bg-slate-500 disabled:text-slate-300"
          >
            {isSubmitting ? 'Submitting...' : 'Submit Order'}
          </button>
        </aside>
      </form>
    </div>
  );
}
