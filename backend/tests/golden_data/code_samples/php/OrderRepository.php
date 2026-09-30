<?php
// Repozytorium zamówień — przykład kodu PHP do generowania testów PHPUnit/Pest (Story 1.55).

declare(strict_types=1);

namespace App\Repositories;

final class OrderRepository
{
    /** @var array<int, array{id: int, paid: bool, amount: float}> */
    private array $orders = [];

    public function add(int $id, float $amount, bool $paid = false): void
    {
        $this->orders[$id] = ['id' => $id, 'paid' => $paid, 'amount' => $amount];
    }

    /** @return array<int, array{id: int, paid: bool, amount: float}> */
    public function findPaid(int $limit = 10): array
    {
        return array_slice(
            array_values(array_filter($this->orders, static fn (array $o): bool => $o['paid'])),
            0,
            $limit,
        );
    }

    public function total(): float
    {
        return array_sum(array_map(static fn (array $o): float => $o['amount'], $this->orders));
    }

    public function count(): int
    {
        return count($this->orders);
    }
}
