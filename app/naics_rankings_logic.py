"""
NAICS Rankings Page Logic

Aggregates company scoring data by NAICS code to show industry-level attractiveness.
"""

import pandas as pd
import streamlit as st
from pathlib import Path


# Cache NAICS descriptions to avoid reloading on every call
_naics_description_cache = None


def _load_naics_descriptions():
    """
    Load NAICS descriptions from multiple sources and cache them.

    Priority order:
    1. Supplementary hardcoded descriptions (for codes missing from files)
    2. naics_metrics.csv (has AI-generated descriptions for scored NAICS codes)
    3. config/naics_codes.csv (has standard NAICS descriptions)
    4. Fallback to generic category names
    """
    global _naics_description_cache

    if _naics_description_cache is not None:
        return _naics_description_cache

    description_map = {}

    # Add supplementary NAICS descriptions for codes not in our CSV files
    supplementary = {
        '1114': 'Greenhouse, Nursery, and Floriculture Production',
        '1119': 'Other Crop Farming',
        '1133': 'Logging',
        '1142': 'Hunting and Trapping',
        '1151': 'Support Activities for Crop Production',
        '2212': 'Natural Gas Distribution',
        '3111': 'Animal Food Manufacturing',
        '3114': 'Fruit and Vegetable Preserving and Specialty Food Manufacturing',
        '4231': 'Motor Vehicle and Motor Vehicle Parts and Supplies Merchant Wholesalers',
        '4241': 'Paper and Paper Product Merchant Wholesalers',
        '4244': 'Grocery and Related Product Merchant Wholesalers',
        '4245': 'Farm Product Raw Material Merchant Wholesalers',
        '4248': 'Beer, Wine, and Distilled Alcoholic Beverage Merchant Wholesalers',
        '4412': 'Other Motor Vehicle Dealers',
        '4441': 'Building Material and Supplies Dealers',
        '4491': 'Other General Merchandise Stores',
        '4492': 'Vending Machine Operators',
        '4581': 'Fuel Dealers',
        '4591': 'Farm and Garden Machinery and Equipment Merchant Wholesalers',
        '4592': 'Book Stores and News Dealers',
        '4594': 'Office Supplies, Stationery, and Gift Stores',
        '4595': 'Used Merchandise Stores',
        '4599': 'Other Miscellaneous Store Retailers',
        '4842': 'Specialized Freight Trucking',
        '4861': 'Pipeline Transportation of Crude Oil',
        '5132': 'Cable and Other Subscription Programming',
        '5322': 'Consumer Goods Rental',
        '3256': 'Soap, Cleaning Compound, and Toilet Preparation Manufacturing',
    }
    description_map.update(supplementary)

    # Load from config file first (lower priority)
    config_path = Path("config/naics_codes.csv")
    if config_path.exists():
        try:
            config_df = pd.read_csv(config_path)
            for _, row in config_df.iterrows():
                naics_code = str(int(row['naics_code']))
                description_map[naics_code] = row['description']
        except Exception:
            pass  # Skip if file can't be loaded

    # Load from naics_metrics.csv (higher priority - overwrites config and supplementary)
    metrics_path = Path("data/scoring/naics_metrics.csv")
    if metrics_path.exists():
        try:
            metrics_df = pd.read_csv(metrics_path)
            for _, row in metrics_df.iterrows():
                naics_code = str(int(row['naics_code']))
                desc = row.get('naics_description', '')
                # Only use if it's not a generic "NAICS XXXX" description
                if pd.notna(desc) and not desc.startswith('NAICS ') and desc.strip():
                    description_map[naics_code] = desc
        except Exception:
            pass  # Skip if file can't be loaded

    _naics_description_cache = description_map
    return description_map


def get_naics_description(naics_code):
    """
    Get human-readable description for NAICS code.

    Loads descriptions from naics_metrics.csv and config/naics_codes.csv,
    with fallback to generic category names based on 2-digit NAICS prefix.
    """
    naics_str = str(int(naics_code)) if pd.notna(naics_code) else ''

    if not naics_str:
        return 'Unknown'

    # Try to get description from loaded files
    description_map = _load_naics_descriptions()

    # Try exact match for 4-digit code
    if len(naics_str) >= 4:
        naics_4digit = naics_str[:4]
        if naics_4digit in description_map:
            return description_map[naics_4digit]

    # Try exact match for full code
    if naics_str in description_map:
        return description_map[naics_str]

    # Fallback to category based on first 2 digits
    if naics_str.startswith('11'):
        return f'Agriculture ({naics_str})'
    elif naics_str.startswith('21'):
        return f'Mining ({naics_str})'
    elif naics_str.startswith('22'):
        return f'Utilities ({naics_str})'
    elif naics_str.startswith('23'):
        return f'Construction ({naics_str})'
    elif naics_str.startswith('31') or naics_str.startswith('32') or naics_str.startswith('33'):
        return f'Manufacturing ({naics_str})'
    elif naics_str.startswith('42'):
        return f'Wholesale Trade ({naics_str})'
    elif naics_str.startswith('44') or naics_str.startswith('45'):
        return f'Retail Trade ({naics_str})'
    elif naics_str.startswith('48') or naics_str.startswith('49'):
        return f'Transportation & Warehousing ({naics_str})'
    elif naics_str.startswith('51'):
        return f'Information ({naics_str})'
    elif naics_str.startswith('52'):
        return f'Finance & Insurance ({naics_str})'
    elif naics_str.startswith('53'):
        return f'Real Estate ({naics_str})'
    elif naics_str.startswith('54'):
        return f'Professional Services ({naics_str})'
    elif naics_str.startswith('55'):
        return f'Management of Companies ({naics_str})'
    elif naics_str.startswith('56'):
        return f'Administrative & Support Services ({naics_str})'
    elif naics_str.startswith('61'):
        return f'Educational Services ({naics_str})'
    elif naics_str.startswith('62'):
        return f'Healthcare Services ({naics_str})'
    elif naics_str.startswith('71'):
        return f'Arts & Entertainment ({naics_str})'
    elif naics_str.startswith('72'):
        return f'Accommodation & Food Services ({naics_str})'
    elif naics_str.startswith('81'):
        return f'Other Services ({naics_str})'
    elif naics_str.startswith('92'):
        return f'Public Administration ({naics_str})'
    else:
        return f'NAICS {naics_str}'


def aggregate_naics_rankings(scored_df):
    """
    Load NAICS rankings from the metrics file generated by scoring script.

    Args:
        scored_df: DataFrame with scored companies (used for company counts)

    Returns:
        DataFrame with one row per NAICS code (6-digit), sorted by attractiveness
    """
    from pathlib import Path

    # Load NAICS metrics file
    naics_metrics_path = Path("data/scoring/naics_metrics.csv")

    if not naics_metrics_path.exists():
        # Fallback: aggregate from scored companies if metrics file doesn't exist
        import streamlit as st
        st.error(f"NAICS metrics file not found: {naics_metrics_path}. Run scoring script to generate it.")
        return pd.DataFrame()

    naics_df = pd.read_csv(naics_metrics_path)

    # Rename icp_fit_reasoning to reasoning for consistency in UI
    if 'icp_fit_reasoning' in naics_df.columns:
        naics_df['reasoning'] = naics_df['icp_fit_reasoning']
    else:
        naics_df['reasoning'] = None

    # Convert naics_code to string for proper merging later
    naics_df['naics_code'] = naics_df['naics_code'].astype(str)

    # Add company count by grouping scored companies by 4-digit NAICS
    if 'naics_4digit' in scored_df.columns:
        # Use existing naics_4digit column from scored_companies_final.csv
        company_counts = scored_df.groupby('naics_4digit').agg({
            'company_id': 'count',
            'is_customer': 'sum'  # Count customers (is_customer is boolean/int)
        }).reset_index()
        company_counts.columns = ['naics_code', 'company_count', 'customer_count']

        # Ensure naics_code is string for proper merging
        company_counts['naics_code'] = company_counts['naics_code'].astype(str)

        # Merge counts into naics_df
        naics_df = naics_df.merge(company_counts, on='naics_code', how='left')

        # Fill NaN values with 0 for NAICS codes that have no companies
        naics_df['company_count'] = naics_df['company_count'].fillna(0).astype(int)
        naics_df['customer_count'] = naics_df['customer_count'].fillna(0).astype(int)
    else:
        # If naics_4digit column doesn't exist, set defaults
        naics_df['company_count'] = 0
        naics_df['customer_count'] = 0

    naics_df['prospect_count'] = naics_df['company_count'] - naics_df['customer_count']

    # Use NAICS descriptions from CSV if available, otherwise generate them
    if 'naics_description' not in naics_df.columns or naics_df['naics_description'].isna().all():
        naics_df['naics_description'] = naics_df['naics_code'].apply(get_naics_description)
    else:
        # Fill missing or generic descriptions with better ones from our lookup
        naics_df['naics_description'] = naics_df.apply(
            lambda row: get_naics_description(row['naics_code'])
            if pd.isna(row.get('naics_description')) or
               str(row.get('naics_description')).startswith('NAICS ') or
               not str(row.get('naics_description')).strip()
            else row['naics_description'],
            axis=1
        )

    # Sort by attractiveness score
    naics_df = naics_df.sort_values('attractiveness_score', ascending=False)

    # Reorder columns - show component scores instead of company stats
    # Exclude rank and penetration_opp_score (not used in scoring)
    naics_df = naics_df[[
        'naics_code',
        'naics_description',
        'attractiveness_score',
        'company_count',
        'customer_count',
        'prospect_count',
        'icp_fit_score',
        'profitability_score',
        'market_size_score',
        'market_size_count',
        'churn_health_score',
        'ticket_health_score',
        'reasoning'
    ]]

    return naics_df


def get_search_synonyms():
    """
    Return a dictionary of search term synonyms for industry search.

    When a user searches for a key term, we also search for all its synonyms.
    This helps users find relevant industries more easily.
    """
    return {
        # Healthcare
        'hospital': ['hospital', 'outpatient', 'inpatient', 'medical center', 'clinic', 'healthcare facility'],
        'medical': ['medical', 'health', 'healthcare', 'clinical', 'physician', 'doctor', 'dentist'],
        'care': ['care', 'nursing', 'assisted living', 'residential care'],
        'outpatient': ['outpatient', 'ambulatory', 'clinic', 'medical center'],

        # Education
        'school': ['school', 'education', 'elementary', 'secondary', 'college', 'university', 'academy'],
        'education': ['education', 'school', 'learning', 'academic', 'training'],

        # Construction & Real Estate
        'construction': ['construction', 'building', 'contractor', 'builder'],
        'building': ['building', 'construction', 'facility', 'structure'],
        'real estate': ['real estate', 'property', 'leasing', 'rental'],
        'property': ['property', 'real estate', 'building', 'facility'],

        # Warehousing & Logistics
        'warehouse': ['warehouse', 'warehousing', 'storage', 'distribution', 'logistics'],
        'logistics': ['logistics', 'transportation', 'freight', 'shipping', 'distribution'],
        'trucking': ['trucking', 'freight', 'transportation', 'delivery'],

        # Manufacturing
        'manufacturing': ['manufacturing', 'production', 'factory', 'plant', 'fabrication'],
        'factory': ['factory', 'plant', 'manufacturing', 'production'],

        # Retail & Food
        'retail': ['retail', 'store', 'shop', 'merchandise'],
        'restaurant': ['restaurant', 'food service', 'dining', 'cafe', 'eatery'],
        'grocery': ['grocery', 'supermarket', 'food store'],

        # Services
        'office': ['office', 'professional services', 'administrative'],
        'recreation': ['recreation', 'entertainment', 'amusement', 'leisure'],
        'fitness': ['fitness', 'gym', 'health club', 'recreation'],

        # Facilities
        'facility': ['facility', 'building', 'property', 'location', 'site'],
        'cleaning': ['cleaning', 'janitorial', 'sanitation', 'facilities management'],
    }


def expand_search_query(query):
    """
    Expand a search query to include synonyms.

    Args:
        query: User's search string

    Returns:
        List of search terms including original query and synonyms
    """
    query_lower = query.lower().strip()
    synonyms_dict = get_search_synonyms()

    # Start with the original query
    search_terms = [query_lower]

    # Check if the query matches any synonym key
    if query_lower in synonyms_dict:
        search_terms.extend(synonyms_dict[query_lower])

    # Also check if query is part of a multi-word key (e.g., "real estate")
    for key, values in synonyms_dict.items():
        if query_lower in key or key in query_lower:
            search_terms.extend(values)

    # Remove duplicates while preserving order
    seen = set()
    unique_terms = []
    for term in search_terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return unique_terms


def get_score_color(score):
    """
    Return color for score tier.

    Per PRD:
    - Green (80+)
    - Yellow (60-79)
    - Red (<60)
    """
    if score >= 80:
        return '#28a745'  # Green
    elif score >= 60:
        return '#ffc107'  # Yellow
    else:
        return '#dc3545'  # Red


def metric_with_tooltip(label, value, tooltip_text):
    """
    Display a metric with a hover tooltip using HTML/CSS.

    Args:
        label: The metric label (e.g., "Attractiveness")
        value: The metric value (e.g., "93.8")
        tooltip_text: The tooltip text to show on hover
    """
    # CSS for tooltip styling
    tooltip_css = """
    <style>
    .tooltip-container {
        position: relative;
        display: inline-block;
        margin-bottom: 1rem;
    }
    .tooltip-label {
        color: #808495;
        font-size: 0.875rem;
        font-weight: 400;
        cursor: help;
        border-bottom: 1px dashed #808495;
    }
    .tooltip-value {
        color: #0E1117;
        font-size: 2rem;
        font-weight: 600;
        margin-top: 0.25rem;
    }
    .tooltip-text {
        visibility: hidden;
        width: 300px;
        background-color: #262730;
        color: #FAFAFA;
        text-align: left;
        border-radius: 6px;
        padding: 10px;
        position: absolute;
        z-index: 1000;
        bottom: 125%;
        left: 50%;
        margin-left: -150px;
        opacity: 0;
        transition: opacity 0.3s;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        font-size: 0.875rem;
        line-height: 1.4;
        border: 1px solid #404040;
    }
    .tooltip-text::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #262730 transparent transparent transparent;
    }
    .tooltip-container:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    </style>
    """

    # HTML structure
    html = f"""
    {tooltip_css}
    <div class="tooltip-container">
        <div class="tooltip-label">{label}</div>
        <div class="tooltip-value">{value}</div>
        <span class="tooltip-text">{tooltip_text}</span>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


def display_naics_rankings(scored_df):
    """
    Display NAICS rankings table with sortable columns and click-through.

    Args:
        scored_df: DataFrame with scored companies
    """
    st.title("NAICS Industry Rankings")
    st.markdown("""
    Industries ranked by attractiveness score, combining ICP fit, OpenWorks operational metrics
    (revenue concentration, building count, revenue per building), market size, and customer health metrics
    (churn and support tickets).
    """)

    # Add data dictionary at the top
    with st.expander("📖 Score Component Dictionary - Understanding Industry Metrics", expanded=False):
        st.markdown("""
        Each industry is evaluated across multiple dimensions to calculate an overall **Attractiveness Score**. Below is a complete explanation of all metrics displayed in the industry rankings.

        | Component | Description | Range | Weight | Example |
        |-----------|-------------|-------|--------|---------|
        | **Attractiveness Score** | Overall industry attractiveness combining all factors below | 0-100 | 100% | **93.8** = Elite tier (top priority), **75.3** = Good opportunity |
        | **ICP Fit Score** | Claude AI assessment of how well this industry aligns with OpenWorks' ideal customer profile | 0-100 | 25% | **92** = Perfect fit (schools, multi-location facilities), **68** = Moderate fit (some internal FM teams) |
        | **Market Size Score** | Nationwide market size - how many locations exist in this industry | 0-100 | 15% | **100.0** = 100,000+ locations (huge market), **71.1** = 3,600 locations (smaller market) |
        | **Market Size Count** | Actual count of locations nationwide for this NAICS code | 1+ | N/A | **230,965** locations (Elementary Schools), **79,218** locations (Hospitals) |
        | **OW Revenue Concentration** | Percentage of OpenWorks' total revenue from this industry | 0-100 | 15% | **100** = 5%+ of total revenue (major vertical), **37** = <1% of revenue (minor presence) |
        | **OW Building Count** | Number of buildings OpenWorks currently serves in this industry | 0-100 | 20% | **100** = 164 buildings (strong footprint), **63** = 11 buildings (emerging presence) |
        | **Revenue per Building** | OpenWorks' average monthly revenue per building in this industry | 0-100 | 5% | **91.8** = $5,550/building (high value), **28.6** = $1,187/building (lower value) |
        | **Churn Health Score** | Customer retention health - lower churn = higher score | 0-100 | 15% | **89.8** = Strong retention, **95.2** = Excellent retention |
        | **Ticket Health Score** | Support ticket quality/volume - fewer/better tickets = higher score | 0-100 | 5% | **55.0** = Moderate support needs, **35.0** = Higher support needs |
        | **Profitability Score** | Industry profit margin from OpenWorks operations (reference only, not used in attractiveness) | 0-100 | 0% | **0.4** = Low/negative margins, **0.44** = Healthy margins |
        | **Companies** | Number of companies in our database for this industry | 0+ | N/A | **29** companies (Elementary Schools), **5** companies (Hospitals) |

        ### Attractiveness Score Formula:
        **Attractiveness = ICP Fit (25%) + Market Size (15%) + OW Revenue Concentration (15%) + OW Building Count (20%) + Revenue per Building (5%) + Churn Health (15%) + Ticket Health (5%)**

        ### Score Interpretation:
        - **90-100**: 🟢 Elite tier - Exceptional opportunity, highest priority
        - **80-89**: 🟢 Strong opportunity - High priority for expansion
        - **70-79**: 🟡 Good opportunity - Medium priority
        - **60-69**: 🟡 Fair opportunity - Consider with caution
        - **<60**: 🔴 Lower priority - Proceed carefully

        ### Key Insights:
        - **ICP Fit**: AI evaluates facility type, multi-location potential, cleaning as non-core function, lack of internal FM teams, and similarity to existing successful customers
        - **OpenWorks Metrics**: Industries with proven success (high revenue, many buildings, good margins) score higher - this reflects real operational experience
        - **Customer Health**: Churn and ticket health reflect how well OpenWorks serves customers in each industry
        - **Market Size**: Larger markets offer more growth potential, but proven success matters more than raw size

        💡 **Pro Tip**: Click on any industry below to see its detailed ICP Fit justification and component breakdown.
        """)

    # Aggregate data
    naics_df = aggregate_naics_rankings(scored_df)

    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Industries", len(naics_df))
    with col2:
        top_score = naics_df['attractiveness_score'].max()
        st.metric("Top Score", f"{top_score:.1f}")
    with col3:
        total_companies = naics_df['company_count'].sum()
        st.metric("Total Companies", f"{total_companies:,}")

    st.markdown("---")

    # Add search box
    search_query = st.text_input(
        "🔍 Search Industries",
        placeholder="Search by NAICS code (e.g., '62' or '6214') or description (e.g., 'hospital', 'construction')...",
        help="Filter industries by NAICS code or description text (case-insensitive)"
    )

    # Apply search filter
    if search_query:
        search_lower = search_query.lower().strip()

        # If search query is all digits, search by NAICS code prefix only
        # Otherwise, search in description and reasoning text with synonym expansion
        if search_query.isdigit():
            # For numeric queries, match NAICS codes that START with the query
            naics_df = naics_df[
                naics_df['naics_code'].astype(str).str.startswith(search_query, na=False)
            ]
        else:
            # For text queries, expand with synonyms and search in description and reasoning
            search_terms = expand_search_query(search_query)

            # Build a filter that matches any of the search terms
            filter_mask = pd.Series([False] * len(naics_df), index=naics_df.index)
            for term in search_terms:
                filter_mask |= (
                    naics_df['naics_description'].astype(str).str.contains(term, case=False, na=False) |
                    naics_df['reasoning'].astype(str).str.contains(term, case=False, na=False)
                )

            naics_df = naics_df[filter_mask]

        if len(naics_df) == 0:
            st.warning(f"No industries found matching '{search_query}'. Try a different search term.")
            st.stop()
        else:
            # Show if synonyms were used
            if not search_query.isdigit() and len(search_terms) > 1:
                st.info(f"Found {len(naics_df)} industry(ies) matching '{search_query}' (including synonyms: {', '.join(search_terms[1:4])}{'...' if len(search_terms) > 4 else ''})")
            else:
                st.info(f"Found {len(naics_df)} industry(ies) matching '{search_query}'")

    # Add sorting controls
    sort_col1, sort_col2 = st.columns([3, 1])
    with sort_col1:
        sort_by = st.selectbox(
            "Sort by",
            options=[
                'attractiveness_score',
                'company_count',
                'icp_fit_score',
                'profitability_score',
                'market_size_score',
                'churn_health_score',
                'ticket_health_score'
            ],
            format_func=lambda x: {
                'attractiveness_score': 'Attractiveness Score',
                'company_count': 'Company Count',
                'icp_fit_score': 'ICP Fit',
                'profitability_score': 'Profitability',
                'market_size_score': 'Market Size',
                'churn_health_score': 'Churn Health',
                'ticket_health_score': 'Ticket Health'
            }[x],
            index=0  # Default to attractiveness_score
        )
    with sort_col2:
        sort_order = st.radio("Order", ['Descending', 'Ascending'], horizontal=True)

    # Apply sorting
    ascending = (sort_order == 'Ascending')
    naics_df_sorted = naics_df.sort_values(sort_by, ascending=ascending)

    # Display table with color coding
    st.markdown("### Industry Rankings")

    # Display industries with expandable reasoning
    for idx, row in naics_df_sorted.iterrows():
        color = get_score_color(row['attractiveness_score'])

        # Create expandable container for each industry
        with st.expander(
            f"**{row['naics_description']}** (NAICS: {row['naics_code']}) — "
            f"Score: {row['attractiveness_score']:.1f}",
            expanded=False
        ):
            # Score metrics in columns with tooltips
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                metric_with_tooltip(
                    "Attractiveness",
                    f"{row['attractiveness_score']:.1f}",
                    "⭐ Overall industry attractiveness (0-100). Combines ICP Fit (25%), Market Size (15%), OW Revenue Concentration (15%), OW Building Count (20%), Revenue/Building (5%), Churn Health (15%), Ticket Health (5%). Higher = more attractive industry for OpenWorks."
                )
                if pd.notna(row.get('icp_fit_score')):
                    metric_with_tooltip(
                        "ICP Fit",
                        f"{row['icp_fit_score']:.1f}",
                        "🤖 Claude AI assessment (0-100) of how well this industry aligns with OpenWorks' ideal customer profile. Evaluates facility needs, multi-location potential, cleaning as non-core function, lack of internal FM teams, and similarity to successful customers. Worth 25% of Attractiveness Score."
                    )

            with col2:
                if pd.notna(row.get('profitability_score')):
                    metric_with_tooltip(
                        "Profitability",
                        f"{row['profitability_score']:.1f}",
                        "💰 Industry profit margin score (0-100) from OpenWorks operations. Based on 0-40% margin mapped to 0-100 score. Reference metric only - NOT included in Attractiveness Score calculation."
                    )
                if pd.notna(row.get('market_size_score')):
                    metric_with_tooltip(
                        "Market Size",
                        f"{row['market_size_score']:.1f}",
                        "📊 Nationwide market size score (0-100) based on DataAxle location counts. Log-scaled: 1 location=0, 100,000+ locations=100. Larger markets = more growth potential. Worth 15% of Attractiveness Score."
                    )

            with col3:
                if pd.notna(row.get('churn_health_score')):
                    metric_with_tooltip(
                        "Churn Health",
                        f"{row['churn_health_score']:.1f}",
                        "🔄 Customer retention health (0-100) based on historical churn predictions. Higher score = lower churn risk = better customer retention in this industry. Worth 15% of Attractiveness Score."
                    )
                if pd.notna(row.get('ticket_health_score')):
                    metric_with_tooltip(
                        "Ticket Health",
                        f"{row['ticket_health_score']:.1f}",
                        "🎫 Support ticket quality/volume score (0-100) from semantic analysis. Higher score = fewer support issues and better service quality in this industry. Worth 5% of Attractiveness Score."
                    )

            with col4:
                metric_with_tooltip(
                    "Companies",
                    f"{row.get('company_count', 0):.0f}",
                    "🏢 Number of companies in our database for this industry. Shows how many prospects are available in this NAICS code. Not used in scoring calculation."
                )
                if pd.notna(row.get('market_size_count')):
                    metric_with_tooltip(
                        "Market Size Count",
                        f"{row.get('market_size_count', 0):,.0f}",
                        "🌍 Actual count of locations nationwide for this NAICS code from DataAxle. Total addressable market size. Reference metric - not directly used in scoring (Market Size Score is the log-scaled version used in calculations)."
                    )

            # ICP Fit Reasoning
            if pd.notna(row.get('reasoning')) and row.get('reasoning'):
                st.markdown("---")
                st.markdown("**🎯 ICP Fit Justification:**")
                # Escape dollar signs to prevent LaTeX rendering in markdown
                reasoning_text = str(row['reasoning']).replace('$', r'\$')
                st.markdown(f"_{reasoning_text}_")
            else:
                st.info("ICP justification not available for this industry.")

            # Navigation button to view companies in this NAICS
            st.markdown("---")
            company_count = int(row.get('company_count', 0))
            if company_count > 0:
                if st.button(
                    f"🔍 View {company_count} Companies in this Industry",
                    key=f"view_naics_{row['naics_code']}",
                    use_container_width=True
                ):
                    # Set session state to pre-filter on the target page
                    st.session_state['naics_filter_from_rankings'] = str(row['naics_code'])
                    st.switch_page("pages/1_ranked_companies.py")
            else:
                st.info("No companies in this industry in the current dataset.")

    return naics_df
