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

shared DimDate =
    CsvTable(
        "DimDate.csv",
        {
            {"DateKey", Int64.Type}, {"Date", type date}, {"Year", Int64.Type},
            {"Quarter", type text}, {"MonthNumber", Int64.Type},
            {"MonthName", type text}, {"YearMonth", type text},
            {"YearMonthSort", Int64.Type}
        }
    );

shared DimProduct =
    CsvTable(
        "DimProduct.csv",
        {
            {"ProductKey", Int64.Type}, {"ProductName", type text},
            {"ManufacturingPrice", type number}
        }
    );

shared DimCountry =
    CsvTable(
        "DimCountry.csv",
        {{"CountryKey", Int64.Type}, {"CountryName", type text}}
    );

shared DimSegment =
    CsvTable(
        "DimSegment.csv",
        {{"SegmentKey", Int64.Type}, {"SegmentName", type text}}
    );

shared DimDiscountBand =
    CsvTable(
        "DimDiscountBand.csv",
        {{"DiscountBandKey", Int64.Type}, {"DiscountBand", type text}}
    );

shared FactSales =
    CsvTable(
        "FactSales.csv",
        {
            {"FactRowID", Int64.Type}, {"DateKey", Int64.Type},
            {"ProductKey", Int64.Type}, {"CountryKey", Int64.Type},
            {"SegmentKey", Int64.Type}, {"DiscountBandKey", Int64.Type},
            {"UnitsSold", type number}, {"ManufacturingPrice", type number},
            {"SalePrice", type number}, {"GrossSales", type number},
            {"Discounts", type number}, {"NetSales", type number},
            {"COGS", type number}, {"Profit", type number}
        }
    );
