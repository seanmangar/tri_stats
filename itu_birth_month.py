import json
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import requests  # pip install requests
from scipy.stats import chisquare

from country_continent_alpha import convert_country_alpha2_to_continent, convert_country_alpha2_to_country_name
from utils import json_load, reference_month_of_birth_path, data_dir, res_dir, add_watermark

# todo: is it the correct way to set the math fonts?
plt.rcParams["font.family"] = "monospace"  # todo: set in global config
plt.rcParams['mathtext.default'] = 'rm'
plt.rcParams['mathtext.fontset'] = 'cm'  # "stix

url_prefix = "https://api.triathlon.org/v1/"

with open("api_key.txt", "r") as f:
    api_key = f.readline()
headers = {'apikey': api_key}


def get_request(url, params=""):
    print(url)
    response = requests.request("GET", url, headers=headers, params=params)
    d = json.loads(response.text)
    d = d["data"]
    return d


def get_rankings(ranking_id: int):
    saving_path = data_dir / "rankings" / f"rankings_{ranking_id}.csv"
    saving_path.parent.mkdir(parents=True, exist_ok=True)
    # check if ranking_id has already been retrieved and saved
    if saving_path.exists():
        df = pd.read_csv(saving_path)
        return df

    url_suffix = f"rankings/{ranking_id}"
    res = get_request(url_prefix + url_suffix)
    df = pd.DataFrame(res["rankings"])
    df.to_csv(saving_path)
    return df


def run_chi_square_test(
        observed_freq,
        expected_freq,
        h0: str,
        h1: str,
        title: str = "",
        threshold=0.05
):
    print(f"{observed_freq.sum() = } vs {expected_freq.sum() = }")
    # perform Chi-square test
    chi2_stat, p_value = chisquare(observed_freq, expected_freq)
    chi2_stat_check = np.sum(np.square(observed_freq.values - expected_freq) / expected_freq)

    # print a markdown table
    df_table = pd.DataFrame([observed_freq.tolist(), expected_freq], columns=["Q1", "Q2", "Q3", "Q4"]).T
    df_table.columns = ["OBSERVED (ITU)", "EXPECTED (UN)"]
    print(df_table.to_markdown(colalign=["center"] * (1 + len(df_table.columns))))

    df_table["DIFF"] = df_table["OBSERVED (ITU)"] - df_table["EXPECTED (UN)"]
    df_table["DIFF^2"] = df_table["DIFF"] * df_table["DIFF"]
    df_table["DIFF^2 / EXPECTED"] = df_table["DIFF^2"] / df_table["EXPECTED (UN)"]
    sum_of_diff_squares_normed = df_table["DIFF^2 / EXPECTED"].sum()
    print(df_table.to_markdown(colalign=["center"] * (1 + len(df_table.columns))))

    print(f"- `SUM OF [DIFF^2 / EXPECTED]` = " + "`" + " + ".join([f"{x:.4f}" for x in df_table['DIFF^2 / EXPECTED']]) + f"` = **`{sum_of_diff_squares_normed:.2f}`**")

    assert abs(chi2_stat - chi2_stat_check) < 1e-6, f"{chi2_stat = } vs {chi2_stat_check = }"

    print(f"\n{'--- ' * 6}")
    print(f"{title = }")
    print(f"\tchi-square statistic: {chi2_stat:.2f}")
    print(f"\tp-value: {p_value:.7f}")
    print(f"\tthreshold: {threshold:.7f}")
    if p_value < threshold:
        print(f"Reject H0: {h1}")
    else:
        print(f"Fail to reject H0: {h0}")
    print(f"{'--- ' * 12}\n")


def main():
    df = None

    ranking_ids = list(range(11, 28))
    ranking_ids.extend(list(range(35, 44)))

    # ranking_ids = [23, 24]  # European juniors

    for ranking_id in ranking_ids:
        df_tmp = get_rankings(ranking_id=ranking_id)
        # print(df_tmp.head(5))

        # n_athletes = 10
        # for athlete in df_tmp[:n_athletes].itertuples():
        #     print(f"{athlete.rank:<3} {athlete.athlete_id:<7.0f} ({athlete.athlete_noc}) "
        #           f"({athlete.athlete_age:.0f}) ({athlete.dob}) {athlete.athlete_title}")

        if df is None:
            df = df_tmp
        else:
            df = pd.concat([df, df_tmp])

    print(f"len before cleaning: {len(df):,}")

    # remove duplicates based on athlete_id
    df = df.drop_duplicates(subset="athlete_id")
    print(f"len after drop_duplicates: {len(df):,}")

    # add column for month of birth from dob (e.g. "2020-01-01" -> "01")
    df["month_of_birth"] = df["dob"].apply(lambda x: str(x)[5:7])

    # remove entries with month == ""
    print(f"dropping {len(df[df['month_of_birth'] == ''])} athletes without DOB")
    df = df[df["month_of_birth"] != ""]

    assert sorted(df["month_of_birth"].unique()) == ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
                                                     "12"], df["month_of_birth"].unique()
    df["month_of_birth"] = df["month_of_birth"].astype(int)
    assert sorted(df["month_of_birth"].unique()) == list(range(1, 13)), df["month_of_birth"].unique()

    # remove entries with age == 1
    df = df[df["athlete_age"] != 1]

    # convert athlete_age from float to int
    df["athlete_age"] = df["athlete_age"].astype(int)
    print(f"youngest: {df['athlete_age'].min():.0f}")
    print(f"oldest  : {df['athlete_age'].max():.0f}")

    print(f"len after cleaning: {len(df):,}")

    # ### filter

    # todo: try to filter by country / ranking (performance)
    # df = df[df["athlete_noc"] == "FRA"]

    # ### plot age distribution

    fig = plt.figure(figsize=(12, 12))

    # todo: set in config
    age_min = 15
    age_max = 45

    # plot histogram of athlete_age column. todo: exercise: can it be modelled? skewness?
    athlete_age = df["athlete_age"].value_counts().sort_index()
    # add missing ages with 0 as value
    athlete_age = athlete_age.reindex(range(0, max(athlete_age.index.max(), age_max) + 1), fill_value=0)
    athlete_age.plot.bar(color="deepskyblue")
    plt.axvline(age_min, linestyle="dotted", color="navy", label="kept interval")
    plt.axvline(age_max, linestyle="dotted", color="navy")
    plt.legend()
    plt.title(f"AGE\n{len(df):,} athletes\nAverage: {df['athlete_age'].mean():.1f}", fontsize=20)
    plt.xlabel("")

    plt.tight_layout()
    add_watermark(fig, y=0.95)
    plt.savefig(str(res_dir / "age.png"), dpi=300)

    # plt.show()

    # ### filter

    df = df[(age_min <= df["athlete_age"]) & (df["athlete_age"] <= age_max)]
    n_athletes = len(df)
    print(f"len after age-filter: {n_athletes}")

    # ### plot - country

    fig = plt.figure(figsize=(12, 12))

    plt.title(f'CONTINENT\nof athletes considered for the analysis "Month/Quarter of Birth"\n({n_athletes:,} athletes)', fontsize=20)
    country_value_counts = df[
        # "athlete_noc"
        "athlete_country_isoa2"
        # "athlete_country_name"
    ].value_counts()
    dict(country_value_counts)

    df["athlete_continent"] = df["athlete_country_isoa2"].apply(lambda x: convert_country_alpha2_to_continent(x))
    continent_value_counts = df["athlete_continent"].value_counts()
    continent_value_counts.plot.bar(color="deepskyblue", edgecolor="black")

    plt.xticks(rotation=45, ha="right")

    plt.ylabel("count".upper())
    plt.xlabel("")

    continent_text = {}
    for continent in continent_value_counts.index:
        countries_counts = df[df["athlete_continent"] == continent]["athlete_country_isoa2"].value_counts()
        # take the 3 largest countries
        countries_counts = countries_counts.sort_values(ascending=False).head(5)

        dict(countries_counts)
        country_names_counts = {
            convert_country_alpha2_to_country_name(k) : v
            for k, v in dict(countries_counts).items()
        }
        print(f"{continent}: {country_names_counts}")
        continent_text[continent] = country_names_counts

    for index, (continent, values) in enumerate(continent_text.items()):
        txt = "\n".join(f"{k}: {v}" for k, v in values.items())
        txt += "\n..."
        plt.text(
            index,
            continent_value_counts[index] + 20,
            txt,
            ha="center",
            fontsize=8,
        )

    # add percentage for each bar
    for index, (continent, value) in enumerate(continent_value_counts.items()):
        plt.text(
            index,
            value - 40,
            f"{value / n_athletes * 100:.1f}%",
            ha="center",
            fontsize=10,
        )

    # set y max
    plt.ylim(0, continent_value_counts.max() + 200)

    plt.tight_layout()
    add_watermark(fig, y=0.98)
    plt.savefig(str(res_dir / "birth_continents.png"), dpi=300)

    # plt.show()

    # ### plot - month of birth

    fig = plt.figure(figsize=(12, 12))

    expected_month_freq = np.array(json_load(
        p=reference_month_of_birth_path
    ))

    observed_month_freq = 100 * df["month_of_birth"].value_counts(
        normalize=True  # use percentage
    ).sort_index()

    plt.title(f"MONTH OF BIRTH\n({n_athletes:,} athletes)", fontsize=20)
    plt.bar(range(12), expected_month_freq, color="gray", alpha=0.5, label="expected (data: UN)", edgecolor="black")

    observed_month_freq.plot.bar(label="observed (data: ITU)", color="deepskyblue", edgecolor="black")  # pd.Series

    for index, value in observed_month_freq.items():
        plt.text(
            index - 1,
            value + 0.1,
            f"{value:.2f}%",
            ha="center",
        )

    plt.xticks(rotation=0)
    plt.yticks(range(0, int(max(observed_month_freq.max(), 10)) + 1))
    plt.ylabel("percent".upper())
    plt.xlabel("")

    plt.grid(axis="y")

    plt.title(f"MONTH OF BIRTH\n({n_athletes:,} athletes)", fontsize=18)
    plt.axhline(100 / 12, linestyle="-.", linewidth=2, color="dodgerblue", label=f"uniform: {100 / 12:.1f}%")
    plt.legend()

    plt.tight_layout()
    add_watermark(fig)
    plt.savefig(str(res_dir / "birth_months.png"), dpi=300)

    # plt.show()

    # ### plot - quarters

    fig = plt.figure(figsize=(12, 12))

    # group the 12 values in 4 groups of 3: (1,2,3) (4,5,6) (7,8,9) (10,11,12)
    df['quarter'] = ((df.month_of_birth - 1) // 3) + 1
    observed_quarter_freq = 100 * df['quarter'].value_counts(
        normalize=True  # use percentage
    ).sort_index()

    tmp_reshaped_arr = expected_month_freq.reshape(4, 3)
    expected_quarter_freq = tmp_reshaped_arr.sum(axis=1)

    plt.bar(range(4), expected_quarter_freq, color="gray", alpha=0.3, label="expected (data: UN)", edgecolor="black")
    observed_quarter_freq.plot.bar(label="observed (data: ITU)", color="deepskyblue", edgecolor="black")
    for index, value in observed_quarter_freq.items():
        plt.text(
            index - 1,
            value + 0.3,
            f"{value:.1f}%",
            color="darkblue",
            ha="center",
        )
    plt.xticks([0, 1, 2, 3], ['Q1\n(90/91 days)', 'Q2\n(91 days)', 'Q3\n(92 days)', 'Q4\n(92 days)'], rotation=0)
    plt.title(f"YEAR-QUARTER OF BIRTH\n({n_athletes:,} athletes)", fontsize=18)
    plt.axhline(100 / 4, linestyle="-.", color="dodgerblue", label=f"uniform: {100 / 4:.1f}%", linewidth=2)
    plt.yticks(range(0, int(max(observed_quarter_freq.max(), 10)) + 2))
    plt.ylabel("percent".upper())
    plt.xlabel("")
    plt.grid(axis="y")
    plt.legend()
    plt.tight_layout()
    add_watermark(fig)
    plt.savefig(str(res_dir / "birth_quarters.png"), dpi=300)
    # plt.show()

    # assert sum(observed_month_freq) == 100
    # assert sum(observed_quarter_freq) == 100

    # ### statistical tests

    # run_chi_square_test(
    #     observed_freq=observed_month_freq * n_athletes / 100,
    #     expected_freq=expected_month_freq / 100 * n_athletes,
    #     title="NON-uniform prior - MONTHS",
    #     h0="The distribution of birth MONTHS among athletes comes from UN data.",
    #     h1="The distribution of birth MONTHS among athletes does not come from UN data."
    # )

    run_chi_square_test(
        observed_freq=observed_quarter_freq * n_athletes / 100,
        expected_freq=expected_quarter_freq / 100 * n_athletes,
        title="NON-uniform prior - QUARTERS",
        h0="The distribution of birth MONTHS among athletes comes from UN data.",
        h1="The distribution of birth MONTHS among athletes does not come from UN data."
    )
    #
    # run_chi_square_test(
    #     observed_freq=observed_month_freq * n_athletes / 100,
    #     expected_freq=np.full(12, n_athletes / 12),
    #     title="UNIFORM prior - MONTHS",
    #     h0="The distribution of birth MONTHS among athletes IS uniform.",
    #     h1="The distribution of birth MONTHS among athletes is NOT uniform."
    # )
    #
    # run_chi_square_test(
    #     observed_freq=observed_quarter_freq * n_athletes / 100,
    #     expected_freq=np.full(4, n_athletes / 4),
    #     title="UNIFORM prior - QUARTERS",
    #     h0="The distribution of birth QUARTERS among athletes IS uniform.",
    #     h1="The distribution of birth QUARTERS among athletes is NOT uniform."
    # )


if __name__ == '__main__':
    main()
