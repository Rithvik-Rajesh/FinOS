import 'package:intl/intl.dart';

/// Client-side mirror of the backend `Money` type: integer minor units + currency.
/// Never uses floating point for storage; formatting is the only place we divide.
class Money {
  const Money(this.amountMinor, this.currency);

  final int amountMinor;
  final String currency;

  factory Money.fromJson(Map<String, dynamic> json) =>
      Money(json['amount_minor'] as int, json['currency'] as String);

  static const Map<String, int> _minorUnits = {'INR': 2, 'USD': 2, 'EUR': 2};

  int get _exponent => _minorUnits[currency] ?? 2;

  double get major => amountMinor / _pow10(_exponent);

  bool get isNegative => amountMinor < 0;

  /// Localized currency string, e.g. "₹1,25,000.00".
  String format({bool compact = false}) {
    final format = compact
        ? NumberFormat.compactCurrency(name: currency, symbol: _symbol)
        : NumberFormat.currency(name: currency, symbol: _symbol, decimalDigits: _exponent);
    return format.format(major);
  }

  String get _symbol => switch (currency) {
        'INR' => '₹',
        'USD' => r'$',
        'EUR' => '€',
        _ => '$currency ',
      };

  static int _pow10(int n) {
    var result = 1;
    for (var i = 0; i < n; i++) {
      result *= 10;
    }
    return result;
  }
}
