/**
 * OrderService — obsluga zamowien e-commerce.
 * Golden data sample dla generatora Mocha/Jest.
 */

class OrderService {
  constructor(paymentGateway, inventoryService) {
    this.paymentGateway = paymentGateway;
    this.inventoryService = inventoryService;
    this.orders = new Map();
  }

  async createOrder(items, customerEmail) {
    if (!items || items.length === 0) {
      throw new Error('Order must contain at least one item');
    }
    if (!customerEmail) {
      throw new Error('Customer email is required');
    }

    const total = this.calculateTotal(items);
    const available = await this.inventoryService.checkAvailability(items);
    if (!available) {
      throw new Error('Some items are not available');
    }

    const paymentResult = await this.paymentGateway.processPayment(total);
    if (!paymentResult.success) {
      throw new Error('Payment failed');
    }

    const order = {
      id: Date.now().toString(),
      items,
      customerEmail,
      total,
      status: 'confirmed',
      createdAt: new Date().toISOString(),
    };

    this.orders.set(order.id, order);
    return order;
  }

  calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }

  getOrder(orderId) {
    return this.orders.get(orderId) || null;
  }

  cancelOrder(orderId) {
    const order = this.orders.get(orderId);
    if (!order) {
      return false;
    }
    if (order.status === 'shipped') {
      throw new Error('Cannot cancel shipped order');
    }
    order.status = 'cancelled';
    return true;
  }
}

module.exports = OrderService;
