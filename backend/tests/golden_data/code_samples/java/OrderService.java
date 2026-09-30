package com.example.order;

import com.example.model.Order;
import com.example.model.OrderItem;
import com.example.repository.OrderRepository;
import com.example.service.PaymentService;
import com.example.service.NotificationService;

import java.util.List;

/**
 * Serwis zamowien — probka z mockami DB, platnosci, powiadomien.
 */
public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentService paymentService;
    private final NotificationService notificationService;

    public OrderService(OrderRepository orderRepository, PaymentService paymentService, NotificationService notificationService) {
        this.orderRepository = orderRepository;
        this.paymentService = paymentService;
        this.notificationService = notificationService;
    }

    public Order createOrder(List<OrderItem> items, String customerEmail) {
        if (items == null || items.isEmpty()) {
            throw new IllegalArgumentException("Order must have items");
        }
        double total = items.stream().mapToDouble(OrderItem::getPrice).sum();
        Order order = new Order(items, total, customerEmail);
        Order saved = orderRepository.save(order);

        boolean paid = paymentService.processPayment(saved.getId(), total);
        if (!paid) {
            throw new RuntimeException("Payment failed");
        }

        notificationService.sendConfirmation(customerEmail, saved.getId());
        return saved;
    }

    public Order getOrder(Long id) {
        return orderRepository.findById(id);
    }

    public void cancelOrder(Long id) {
        Order order = orderRepository.findById(id);
        if (order == null) {
            throw new IllegalArgumentException("Order not found");
        }
        paymentService.refund(order.getId(), order.getTotal());
        orderRepository.delete(order);
    }
}
