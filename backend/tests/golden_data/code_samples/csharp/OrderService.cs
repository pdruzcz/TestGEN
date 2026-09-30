namespace MyApp.Services;

using System.Collections.Generic;
using MyApp.Data;

/// <summary>Service zarzadzajacy zamowieniami.</summary>
public class OrderService
{
    private readonly IOrderRepository _orderRepo;
    private readonly INotificationService _notificationService;

    public OrderService(IOrderRepository orderRepo, INotificationService notificationService)
    {
        _orderRepo = orderRepo;
        _notificationService = notificationService;
    }

    public Order CreateOrder(string customerId, List<OrderItem> items)
    {
        if (string.IsNullOrEmpty(customerId)) throw new ArgumentException("Customer ID required");
        if (items == null || items.Count == 0) throw new ArgumentException("Order must have items");

        var order = new Order
        {
            CustomerId = customerId,
            Items = items,
            Status = "pending"
        };
        _orderRepo.Save(order);
        _notificationService.SendNotification(customerId, "Order created");
        return order;
    }

    public bool CancelOrder(string orderId)
    {
        var order = _orderRepo.FindById(orderId);
        if (order == null) return false;
        if (order.Status == "shipped") throw new InvalidOperationException("Cannot cancel shipped order");
        order.Status = "cancelled";
        _orderRepo.Update(order);
        return true;
    }
}

public class Order
{
    public string Id { get; set; } = "";
    public string CustomerId { get; set; } = "";
    public List<OrderItem> Items { get; set; } = new();
    public string Status { get; set; } = "pending";
}

public class OrderItem
{
    public string ProductId { get; set; } = "";
    public int Quantity { get; set; }
    public decimal Price { get; set; }
}
