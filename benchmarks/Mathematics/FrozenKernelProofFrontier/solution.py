"""Cap-length valid proofs. Returning them scores zero.

The first five lines prove goal → goal. The reference derivation is not a prefix of
this file: taking a compiled-size prefix is not a proof of the theorem.
"""
import json
from copy import deepcopy

PADDED = json.loads(r"""
{
  "identity": [
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          "A",
          "A"
        ],
        "Y": [
          "imp",
          [
            "imp",
            "A",
            "A"
          ],
          [
            "imp",
            "A",
            "A"
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "imp",
          "A",
          "A"
        ],
        "Y": [
          "imp",
          [
            "imp",
            "A",
            "A"
          ],
          [
            "imp",
            "A",
            "A"
          ]
        ],
        "Z": [
          "imp",
          "A",
          "A"
        ]
      }
    },
    {
      "mp": [
        0,
        1
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          "A",
          "A"
        ],
        "Y": [
          "imp",
          "A",
          "A"
        ]
      }
    },
    {
      "mp": [
        3,
        2
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": "A",
        "Y": [
          "imp",
          "A",
          "A"
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": "A",
        "Y": [
          "imp",
          "A",
          "A"
        ],
        "Z": "A"
      }
    },
    {
      "mp": [
        5,
        6
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": "A",
        "Y": "A"
      }
    },
    {
      "mp": [
        8,
        7
      ]
    },
    {
      "mp": [
        9,
        4
      ]
    },
    {
      "mp": [
        10,
        4
      ]
    },
    {
      "mp": [
        11,
        4
      ]
    },
    {
      "mp": [
        12,
        4
      ]
    },
    {
      "mp": [
        13,
        4
      ]
    },
    {
      "mp": [
        14,
        4
      ]
    },
    {
      "mp": [
        15,
        4
      ]
    },
    {
      "mp": [
        16,
        4
      ]
    },
    {
      "mp": [
        17,
        4
      ]
    },
    {
      "mp": [
        18,
        4
      ]
    },
    {
      "mp": [
        19,
        4
      ]
    },
    {
      "mp": [
        20,
        4
      ]
    },
    {
      "mp": [
        21,
        4
      ]
    },
    {
      "mp": [
        22,
        4
      ]
    },
    {
      "mp": [
        23,
        4
      ]
    },
    {
      "mp": [
        24,
        4
      ]
    },
    {
      "mp": [
        25,
        4
      ]
    },
    {
      "mp": [
        26,
        4
      ]
    },
    {
      "mp": [
        27,
        4
      ]
    },
    {
      "mp": [
        28,
        4
      ]
    },
    {
      "mp": [
        29,
        4
      ]
    },
    {
      "mp": [
        30,
        4
      ]
    },
    {
      "mp": [
        31,
        4
      ]
    },
    {
      "mp": [
        32,
        4
      ]
    },
    {
      "mp": [
        33,
        4
      ]
    },
    {
      "mp": [
        34,
        4
      ]
    },
    {
      "mp": [
        35,
        4
      ]
    },
    {
      "mp": [
        36,
        4
      ]
    },
    {
      "mp": [
        37,
        4
      ]
    },
    {
      "mp": [
        38,
        4
      ]
    },
    {
      "mp": [
        39,
        4
      ]
    },
    {
      "mp": [
        40,
        4
      ]
    },
    {
      "mp": [
        41,
        4
      ]
    },
    {
      "mp": [
        42,
        4
      ]
    },
    {
      "mp": [
        43,
        4
      ]
    },
    {
      "mp": [
        44,
        4
      ]
    },
    {
      "mp": [
        45,
        4
      ]
    },
    {
      "mp": [
        46,
        4
      ]
    },
    {
      "mp": [
        47,
        4
      ]
    },
    {
      "mp": [
        48,
        4
      ]
    },
    {
      "mp": [
        49,
        4
      ]
    },
    {
      "mp": [
        50,
        4
      ]
    },
    {
      "mp": [
        51,
        4
      ]
    },
    {
      "mp": [
        52,
        4
      ]
    },
    {
      "mp": [
        53,
        4
      ]
    },
    {
      "mp": [
        54,
        4
      ]
    },
    {
      "mp": [
        55,
        4
      ]
    },
    {
      "mp": [
        56,
        4
      ]
    },
    {
      "mp": [
        57,
        4
      ]
    },
    {
      "mp": [
        58,
        4
      ]
    },
    {
      "mp": [
        59,
        4
      ]
    },
    {
      "mp": [
        60,
        4
      ]
    },
    {
      "mp": [
        61,
        4
      ]
    },
    {
      "mp": [
        62,
        4
      ]
    }
  ],
  "conjunction_swap": [
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "B",
            "A"
          ]
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              "A",
              "B"
            ],
            [
              "and",
              "B",
              "A"
            ]
          ],
          [
            "imp",
            [
              "and",
              "A",
              "B"
            ],
            [
              "and",
              "B",
              "A"
            ]
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "B",
            "A"
          ]
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              "A",
              "B"
            ],
            [
              "and",
              "B",
              "A"
            ]
          ],
          [
            "imp",
            [
              "and",
              "A",
              "B"
            ],
            [
              "and",
              "B",
              "A"
            ]
          ]
        ],
        "Z": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "B",
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        0,
        1
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "B",
            "A"
          ]
        ],
        "Y": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "B",
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        3,
        2
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "A",
            "B"
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          [
            "and",
            "A",
            "B"
          ]
        ],
        "Z": [
          "and",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        5,
        6
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": [
          "and",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        8,
        7
      ]
    },
    {
      "axiom": "ANDEL",
      "subst": {
        "X": "A",
        "Y": "B"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "and",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        10,
        11
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": [
          "and",
          "A",
          "B"
        ],
        "Z": "A"
      }
    },
    {
      "mp": [
        12,
        13
      ]
    },
    {
      "mp": [
        9,
        14
      ]
    },
    {
      "axiom": "ANDER",
      "subst": {
        "X": "A",
        "Y": "B"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            "A",
            "B"
          ],
          "B"
        ],
        "Y": [
          "and",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        16,
        17
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": [
          "and",
          "A",
          "B"
        ],
        "Z": "B"
      }
    },
    {
      "mp": [
        18,
        19
      ]
    },
    {
      "mp": [
        9,
        20
      ]
    },
    {
      "axiom": "ANDI",
      "subst": {
        "X": "B",
        "Y": "A"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          "B",
          [
            "imp",
            "A",
            [
              "and",
              "B",
              "A"
            ]
          ]
        ],
        "Y": [
          "and",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        22,
        23
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": "B",
        "Z": [
          "imp",
          "A",
          [
            "and",
            "B",
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        24,
        25
      ]
    },
    {
      "mp": [
        21,
        26
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          "A",
          "B"
        ],
        "Y": "A",
        "Z": [
          "and",
          "B",
          "A"
        ]
      }
    },
    {
      "mp": [
        27,
        28
      ]
    },
    {
      "mp": [
        15,
        29
      ]
    },
    {
      "mp": [
        30,
        4
      ]
    },
    {
      "mp": [
        31,
        4
      ]
    },
    {
      "mp": [
        32,
        4
      ]
    },
    {
      "mp": [
        33,
        4
      ]
    },
    {
      "mp": [
        34,
        4
      ]
    },
    {
      "mp": [
        35,
        4
      ]
    },
    {
      "mp": [
        36,
        4
      ]
    },
    {
      "mp": [
        37,
        4
      ]
    },
    {
      "mp": [
        38,
        4
      ]
    },
    {
      "mp": [
        39,
        4
      ]
    },
    {
      "mp": [
        40,
        4
      ]
    },
    {
      "mp": [
        41,
        4
      ]
    },
    {
      "mp": [
        42,
        4
      ]
    },
    {
      "mp": [
        43,
        4
      ]
    },
    {
      "mp": [
        44,
        4
      ]
    },
    {
      "mp": [
        45,
        4
      ]
    },
    {
      "mp": [
        46,
        4
      ]
    },
    {
      "mp": [
        47,
        4
      ]
    },
    {
      "mp": [
        48,
        4
      ]
    },
    {
      "mp": [
        49,
        4
      ]
    },
    {
      "mp": [
        50,
        4
      ]
    },
    {
      "mp": [
        51,
        4
      ]
    },
    {
      "mp": [
        52,
        4
      ]
    },
    {
      "mp": [
        53,
        4
      ]
    },
    {
      "mp": [
        54,
        4
      ]
    },
    {
      "mp": [
        55,
        4
      ]
    },
    {
      "mp": [
        56,
        4
      ]
    },
    {
      "mp": [
        57,
        4
      ]
    },
    {
      "mp": [
        58,
        4
      ]
    },
    {
      "mp": [
        59,
        4
      ]
    },
    {
      "mp": [
        60,
        4
      ]
    },
    {
      "mp": [
        61,
        4
      ]
    },
    {
      "mp": [
        62,
        4
      ]
    }
  ],
  "packed_composition": [
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          "C"
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              [
                "and",
                [
                  "imp",
                  "B",
                  "C"
                ],
                "A"
              ]
            ],
            "C"
          ],
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              [
                "and",
                [
                  "imp",
                  "B",
                  "C"
                ],
                "A"
              ]
            ],
            "C"
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          "C"
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              [
                "and",
                [
                  "imp",
                  "B",
                  "C"
                ],
                "A"
              ]
            ],
            "C"
          ],
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              [
                "and",
                [
                  "imp",
                  "B",
                  "C"
                ],
                "A"
              ]
            ],
            "C"
          ]
        ],
        "Z": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          "C"
        ]
      }
    },
    {
      "mp": [
        0,
        1
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          "C"
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          "C"
        ]
      }
    },
    {
      "mp": [
        3,
        2
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ]
        ],
        "Z": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        5,
        6
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        8,
        7
      ]
    },
    {
      "axiom": "ANDEL",
      "subst": {
        "X": [
          "imp",
          "A",
          "B"
        ],
        "Y": [
          "and",
          [
            "imp",
            "B",
            "C"
          ],
          "A"
        ]
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          [
            "imp",
            "A",
            "B"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        10,
        11
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Z": [
          "imp",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        12,
        13
      ]
    },
    {
      "mp": [
        9,
        14
      ]
    },
    {
      "axiom": "ANDER",
      "subst": {
        "X": [
          "imp",
          "A",
          "B"
        ],
        "Y": [
          "and",
          [
            "imp",
            "B",
            "C"
          ],
          "A"
        ]
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            [
              "and",
              [
                "imp",
                "B",
                "C"
              ],
              "A"
            ]
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        16,
        17
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Z": [
          "and",
          [
            "imp",
            "B",
            "C"
          ],
          "A"
        ]
      }
    },
    {
      "mp": [
        18,
        19
      ]
    },
    {
      "mp": [
        9,
        20
      ]
    },
    {
      "axiom": "ANDEL",
      "subst": {
        "X": [
          "imp",
          "B",
          "C"
        ],
        "Y": "A"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ],
          [
            "imp",
            "B",
            "C"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        22,
        23
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "B",
            "C"
          ],
          "A"
        ],
        "Z": [
          "imp",
          "B",
          "C"
        ]
      }
    },
    {
      "mp": [
        24,
        25
      ]
    },
    {
      "mp": [
        21,
        26
      ]
    },
    {
      "axiom": "ANDER",
      "subst": {
        "X": [
          "imp",
          "B",
          "C"
        ],
        "Y": "A"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ],
          "A"
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "mp": [
        28,
        29
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "B",
            "C"
          ],
          "A"
        ],
        "Z": "A"
      }
    },
    {
      "mp": [
        30,
        31
      ]
    },
    {
      "mp": [
        21,
        32
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": "A",
        "Z": "B"
      }
    },
    {
      "mp": [
        15,
        34
      ]
    },
    {
      "mp": [
        33,
        35
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          [
            "and",
            [
              "imp",
              "B",
              "C"
            ],
            "A"
          ]
        ],
        "Y": "B",
        "Z": "C"
      }
    },
    {
      "mp": [
        27,
        37
      ]
    },
    {
      "mp": [
        36,
        38
      ]
    },
    {
      "mp": [
        39,
        4
      ]
    },
    {
      "mp": [
        40,
        4
      ]
    },
    {
      "mp": [
        41,
        4
      ]
    },
    {
      "mp": [
        42,
        4
      ]
    },
    {
      "mp": [
        43,
        4
      ]
    },
    {
      "mp": [
        44,
        4
      ]
    },
    {
      "mp": [
        45,
        4
      ]
    },
    {
      "mp": [
        46,
        4
      ]
    },
    {
      "mp": [
        47,
        4
      ]
    },
    {
      "mp": [
        48,
        4
      ]
    },
    {
      "mp": [
        49,
        4
      ]
    },
    {
      "mp": [
        50,
        4
      ]
    },
    {
      "mp": [
        51,
        4
      ]
    },
    {
      "mp": [
        52,
        4
      ]
    },
    {
      "mp": [
        53,
        4
      ]
    },
    {
      "mp": [
        54,
        4
      ]
    },
    {
      "mp": [
        55,
        4
      ]
    },
    {
      "mp": [
        56,
        4
      ]
    },
    {
      "mp": [
        57,
        4
      ]
    },
    {
      "mp": [
        58,
        4
      ]
    },
    {
      "mp": [
        59,
        4
      ]
    },
    {
      "mp": [
        60,
        4
      ]
    },
    {
      "mp": [
        61,
        4
      ]
    },
    {
      "mp": [
        62,
        4
      ]
    }
  ],
  "modus_ponens_closed": [
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "B"
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              "A"
            ],
            "B"
          ],
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              "A"
            ],
            "B"
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "B"
        ],
        "Y": [
          "imp",
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              "A"
            ],
            "B"
          ],
          [
            "imp",
            [
              "and",
              [
                "imp",
                "A",
                "B"
              ],
              "A"
            ],
            "B"
          ]
        ],
        "Z": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "B"
        ]
      }
    },
    {
      "mp": [
        0,
        1
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "B"
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "B"
        ]
      }
    },
    {
      "mp": [
        3,
        2
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ]
        ]
      }
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ]
        ],
        "Z": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ]
      }
    },
    {
      "mp": [
        5,
        6
      ]
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ]
      }
    },
    {
      "mp": [
        8,
        7
      ]
    },
    {
      "axiom": "ANDEL",
      "subst": {
        "X": [
          "imp",
          "A",
          "B"
        ],
        "Y": "A"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          [
            "imp",
            "A",
            "B"
          ]
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ]
      }
    },
    {
      "mp": [
        10,
        11
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Z": [
          "imp",
          "A",
          "B"
        ]
      }
    },
    {
      "mp": [
        12,
        13
      ]
    },
    {
      "mp": [
        9,
        14
      ]
    },
    {
      "axiom": "ANDER",
      "subst": {
        "X": [
          "imp",
          "A",
          "B"
        ],
        "Y": "A"
      }
    },
    {
      "axiom": "K",
      "subst": {
        "X": [
          "imp",
          [
            "and",
            [
              "imp",
              "A",
              "B"
            ],
            "A"
          ],
          "A"
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ]
      }
    },
    {
      "mp": [
        16,
        17
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Z": "A"
      }
    },
    {
      "mp": [
        18,
        19
      ]
    },
    {
      "mp": [
        9,
        20
      ]
    },
    {
      "axiom": "S",
      "subst": {
        "X": [
          "and",
          [
            "imp",
            "A",
            "B"
          ],
          "A"
        ],
        "Y": "A",
        "Z": "B"
      }
    },
    {
      "mp": [
        15,
        22
      ]
    },
    {
      "mp": [
        21,
        23
      ]
    },
    {
      "mp": [
        24,
        4
      ]
    },
    {
      "mp": [
        25,
        4
      ]
    },
    {
      "mp": [
        26,
        4
      ]
    },
    {
      "mp": [
        27,
        4
      ]
    },
    {
      "mp": [
        28,
        4
      ]
    },
    {
      "mp": [
        29,
        4
      ]
    },
    {
      "mp": [
        30,
        4
      ]
    },
    {
      "mp": [
        31,
        4
      ]
    },
    {
      "mp": [
        32,
        4
      ]
    },
    {
      "mp": [
        33,
        4
      ]
    },
    {
      "mp": [
        34,
        4
      ]
    },
    {
      "mp": [
        35,
        4
      ]
    },
    {
      "mp": [
        36,
        4
      ]
    },
    {
      "mp": [
        37,
        4
      ]
    },
    {
      "mp": [
        38,
        4
      ]
    },
    {
      "mp": [
        39,
        4
      ]
    },
    {
      "mp": [
        40,
        4
      ]
    },
    {
      "mp": [
        41,
        4
      ]
    },
    {
      "mp": [
        42,
        4
      ]
    },
    {
      "mp": [
        43,
        4
      ]
    },
    {
      "mp": [
        44,
        4
      ]
    },
    {
      "mp": [
        45,
        4
      ]
    },
    {
      "mp": [
        46,
        4
      ]
    },
    {
      "mp": [
        47,
        4
      ]
    },
    {
      "mp": [
        48,
        4
      ]
    },
    {
      "mp": [
        49,
        4
      ]
    },
    {
      "mp": [
        50,
        4
      ]
    },
    {
      "mp": [
        51,
        4
      ]
    },
    {
      "mp": [
        52,
        4
      ]
    },
    {
      "mp": [
        53,
        4
      ]
    },
    {
      "mp": [
        54,
        4
      ]
    },
    {
      "mp": [
        55,
        4
      ]
    },
    {
      "mp": [
        56,
        4
      ]
    },
    {
      "mp": [
        57,
        4
      ]
    },
    {
      "mp": [
        58,
        4
      ]
    },
    {
      "mp": [
        59,
        4
      ]
    },
    {
      "mp": [
        60,
        4
      ]
    },
    {
      "mp": [
        61,
        4
      ]
    },
    {
      "mp": [
        62,
        4
      ]
    }
  ]
}
""")


def build_proofs(problem):
    """Return one Hilbert proof per theorem, each of length size_cap."""
    return deepcopy(PADDED)
