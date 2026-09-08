from crawler.recovery.engine import RecoveryEngine


TEST_CASES = [
    (
        "Base64",
        "SGVsbG8gV29ybGQ=",
    ),
    (
        "Hex",
        "48656c6c6f20576f726c64",
    ),
    (
        "URL Encoding",
        "hello%20world",
    ),
    (
        "ROT13",
        "uryyb jbeyq",
    ),
    (
        "Caesar +3",
        "khoor zruog",
    ),
]


def main():
    for name, value in TEST_CASES:
        print("=" * 60)
        print(f"TEST: {name}")
        print(f"INPUT: {value}")

        result = RecoveryEngine.process(value)

        print(f"STATUS: {result.status}")
        print(f"RECOVERED: {result.recovered}")
        print(f"CONFIDENCE: {result.confidence}")
        print(f"OUTPUT: {result.recovered_content}")

        if result.transformations:
            print("TRANSFORMATIONS:")
            for step in result.transformations:
                print(
                    f"  - {step['transformation']}"
                    f" ({step['confidence']:.2f})"
                )

        print()


if __name__ == "__main__":
    main()