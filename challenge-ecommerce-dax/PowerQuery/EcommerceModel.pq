shared DataFolder =
    "C:\replace\with\generated\data\folder" meta
        [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true];

shared CsvTable = (fileName as text, columnTypes as list) as table =>
    let
        Source = Csv.Document(
            File.Contents(DataFolder & "\" & fileName),
            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
        ),
        Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
        Typed = Table.TransformColumnTypes(Headers, columnTypes, "en-US")
    in
        Typed;

shared DimDate = CsvTable("DimDate.csv", {
    {"DateKey", Int64.Type}, {"Date", type date}, {"Year", Int64.Type},
    {"MonthNumber", Int64.Type}, {"MonthName", type text}, {"YearMonth", type text},
    {"YearMonthSort", Int64.Type}
});

shared DimProduct = CsvTable("DimProduct.csv", {
    {"ProductKey", Int64.Type}, {"ProductName", type text},
    {"Category", type text}, {"UnitCost", Currency.Type}, {"ListPrice", Currency.Type}
});

shared DimCustomer = CsvTable("DimCustomer.csv", {
    {"CustomerKey", Int64.Type}, {"CustomerCode", type text},
    {"CustomerType", type text}
});

shared DimPaymentMethod = CsvTable("DimPaymentMethod.csv", {
    {"PaymentMethodKey", Int64.Type}, {"PaymentMethod", type text}
});

shared DimOrderStatus = CsvTable("DimOrderStatus.csv", {
    {"OrderStatusKey", Int64.Type}, {"OrderStatus", type text}
});

shared DimGeography = CsvTable("DimGeography.csv", {
    {"GeographyKey", Int64.Type}, {"StateCode", type text},
    {"StateName", type text}, {"Region", type text}
});

shared FactSales = CsvTable("FactSales.csv", {
    {"OrderItemKey", Int64.Type}, {"OrderID", type text},
    {"DateKey", Int64.Type}, {"ProductKey", Int64.Type},
    {"CustomerKey", Int64.Type}, {"PaymentMethodKey", Int64.Type},
    {"OrderStatusKey", Int64.Type}, {"GeographyKey", Int64.Type},
    {"Quantity", Int64.Type}, {"UnitPrice", Currency.Type},
    {"GrossAmount", Currency.Type}, {"DiscountAmount", Currency.Type},
    {"NetAmount", Currency.Type}, {"UnitCost", Currency.Type},
    {"Profit", Currency.Type}
});
