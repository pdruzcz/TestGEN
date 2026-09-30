<?php
// Serwis faktur — przykład kodu PHP do generowania testów PHPUnit/Pest (Story 1.55).

declare(strict_types=1);

namespace App\Services;

final class InvoiceService
{
    private const VAT_RATE = 0.23;

    /** Rzuca DomainException dla kwoty ujemnej. */
    public function netAmount(float $gross): float
    {
        if ($gross < 0.0) {
            throw new \DomainException('Kwota brutto nie może być ujemna');
        }

        return round($gross / (1.0 + self::VAT_RATE), 2);
    }

    public function vatAmount(float $gross): float
    {
        return round($gross - $this->netAmount($gross), 2);
    }
}
