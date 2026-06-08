(function ($) {
    function toNumber(value) {
        if (value === undefined || value === null || value === "") {
            return 0;
        }
        var cleaned = String(value)
            .replace(/\s/g, "")
            .replace(/\./g, "")
            .replace(",", ".")
            .replace(/[^\d.-]/g, "");
        var parsed = parseFloat(cleaned);
        return isNaN(parsed) ? 0 : parsed;
    }

    function formatNumber(value) {
        return (Math.round(value * 100) / 100).toFixed(2).replace(".", ",");
    }

    function recalcRow($row) {
        var quantidade = toNumber($row.find('input[name$="-quantidade"]').val());
        var valorUnitario = toNumber($row.find('input[name$="-valor_unitario"]').val());
        var desconto = toNumber($row.find('input[name$="-desconto"]').val());
        var bruto = quantidade * valorUnitario;
        var total = bruto - (bruto * desconto / 100);
        var $totalInput = $row.find('input[name$="-valor_total"]');
        if ($totalInput.length) {
            $totalInput.val(formatNumber(total));
        }
    }

    function recalcAll() {
        $('input[name$="-quantidade"], input[name$="-valor_unitario"], input[name$="-desconto"]').each(function () {
            var $row = $(this).closest('.form-row, .inline-related, tr');
            if ($row.length) {
                recalcRow($row);
            }
        });
    }

    $(document).on('input change', 'input[name$="-quantidade"], input[name$="-valor_unitario"], input[name$="-desconto"]', function () {
        recalcRow($(this).closest('.form-row, .inline-related, tr'));
    });

    $(document).on('formset:added', function () {
        recalcAll();
    });

    $(document).ready(function () {
        recalcAll();
    });
})(django.jQuery);
