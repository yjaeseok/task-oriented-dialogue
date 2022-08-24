# Copyright 2021 Google Research.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utils for processing multiwoz dialogue data.

# TODO: Add unit tests
"""

import collections
import dataclasses
import json
import os
from typing import Dict, List, Set

# Use OrderedDict for JSON to preserve field order.
Json = collections.OrderedDict


@dataclasses.dataclass
class MultiwozData:
    """Information from MultiWOZ dataset.

    Attributes:
      train_json: JSON for train dialogues.
      dev_json: JSON for dev dialogues.
      test_json: JSON for test dialogues.
      slot_descriptions: Dict mapping slot name to list of slot descriptions.
    """
    train_json: Json
    dev_json: Json
    test_json: Json
    slot_descriptions: Dict[str, List[str]]


@dataclasses.dataclass
class SlotInfo:
    """Dataclass for information about a slot.

    Attributes:
      is_categorical: Whether this is a categorical or noncategorical slot.
      possible_values: A list of possible values. This is empty if this is a
        noncategorical slot.
    """
    is_categorical: bool
    possible_values: List[str]


@dataclasses.dataclass
class SchemaInfo:
    """Dataclass for information from a schema.

    Attributes:
      slots_by_domain: slots_by_domain[domain][slot_name] has a SlotInfo dataclass
        for that particular domain and slot_name.
    """
    slots_by_domain: Dict[str, Dict[str, SlotInfo]]


def load_data(data_path: str,
              multiwoz_version: str,
              is_trade: bool = False) -> MultiwozData:
    """Loads MultiWOZ dataset.

    Args:
      data_path: Path to the multiwoz dataset.
      multiwoz_version: The version of the multiwoz dataset.
      is_trade: Whether the data is trade-preprocessed or not.

    Returns:
      A dataclass object storing the loaded dataset.
    """
    # Load dialogue data.
    if is_trade:
        with open(os.path.join(data_path, 'train_dials.json')) as f:
            train_json = Json()
            for d in json.loads(f.read().lower(), object_pairs_hook=Json):
                train_json[d['dialogue_idx']] = d

        with open(os.path.join(data_path, 'dev_dials.json')) as f:
            dev_json = Json()
            for d in json.loads(f.read().lower(), object_pairs_hook=Json):
                dev_json[d['dialogue_idx']] = d

        with open(os.path.join(data_path, 'test_dials.json')) as f:
            test_json = Json()
            for d in json.loads(f.read().lower(), object_pairs_hook=Json):
                test_json[d['dialogue_idx']] = d

    else:
        with open(os.path.join(data_path, 'data.json')) as f:
            # Load using collections.OrderedDict to keep order the same as JSON.
            json_data = json.loads(f.read().lower(), object_pairs_hook=Json)

        # Different MultiWOZ versions have different (val|test)ListFile extensions
        # but both can be parsed as a text file containing a list of dialog ids.
        extension = 'json' if multiwoz_version == '2.4' else 'txt'
        with open(os.path.join(data_path,
                               f'valListFile.{extension}')) as f:
            dev_ids = {line.lower().rstrip() for line in f}
        with open(
                os.path.join(data_path, f'testListFile.{extension}')) as f:
            test_ids = {line.lower().rstrip() for line in f}

        train_json, dev_json, test_json = {}, {}, {}
        for dialog_idx, dialog_json in json_data.items():
            if dialog_idx in dev_ids:
                dev_json[dialog_idx] = dialog_json
            elif dialog_idx in test_ids:
                test_json[dialog_idx] = dialog_json
            else:
                train_json[dialog_idx] = dialog_json

    # Load slot descriptions. Note that 2.4 doesn't come with a
    # slot_descriptions.json file. Copy the 2.1 file to avoid an error
    with open(os.path.join(data_path, 'slot_descriptions.json')) as f:
        slot_descriptions_raw = json.loads(f.read().lower(), object_pairs_hook=Json)
        slot_descriptions = {}
        for key, val in slot_descriptions_raw.items():
            # To be consistent with the keys from extract_belief_state(), rename
            # "book" slots. e.g. "hotel-book people" -> "hotel-people".
            key = key.replace('book ', '')
            # slot_descriptions.json has a "bus-arriveby" slot that doesn't actually
            # exist.
            if key in ('bus-arriveby', 'bus-people'):
                continue

            slot_descriptions[key] = val

    return MultiwozData(train_json, dev_json, test_json, slot_descriptions)


def load_data_for_dstc(train_path, dev_path, slot_path) -> MultiwozData:
    with open(train_path) as f:
        train_json = json.loads(f.read().lower(), object_pairs_hook=Json)

    with open(dev_path) as f:
        dev_json = json.loads(f.read().lower(), object_pairs_hook=Json)

    # TODO : test_json

    with open(slot_path) as f:
        slot_descriptions_raw = json.loads(f.read().lower(), object_pairs_hook=Json)
        slot_descriptions = {}
        for key, val in slot_descriptions_raw.items():
            # To be consistent with the keys from extract_belief_state(), rename
            # "book" slots. e.g. "hotel-book people" -> "hotel-people".
            key = key.replace('book ', '')
            # slot_descriptions.json has a "bus-arriveby" slot that doesn't actually
            # exist.
            if key in ('bus-arriveby', 'bus-people'):
                continue

            slot_descriptions[key] = val

    return MultiwozData(train_json, dev_json, Json(), slot_descriptions)


def load_schema(schema_path: str) -> SchemaInfo:
    """Load information from MultiWOZ schema file."""
    with open(schema_path) as f:
        schema_json = json.loads(f.read().lower(), object_pairs_hook=Json)

    slots_by_domain = {}
    for service in schema_json:
        domain = service['service_name']
        slots_by_domain[domain] = {}
        for slot in service['slots']:
            is_categorical = slot['is_categorical']
            if is_categorical:
                possible_values = slot['possible_values']
            else:
                possible_values = []

            # Don't consider numerical categorical slots as categorical.
            if is_categorical and all([_.isdigit() for _ in possible_values]):
                is_categorical = False
                possible_values = []

            # To be consistent with the slots in the dialogue, rename
            # "book" slots. e.g. "hotel-book people" -> "hotel-people".
            slot_name = slot['name'].replace('book', '')
            slots_by_domain[domain][slot_name] = SlotInfo(
                is_categorical=is_categorical, possible_values=possible_values)
    return SchemaInfo(slots_by_domain)


def load_schema_for_dstc(schemaless_path) -> SchemaInfo:
    """Load information from MultiWOZ schema file."""
    with open(schemaless_path) as f:
        schema_json = json.loads(f.read().lower(), object_pairs_hook=Json)

    slots_by_domain = {}
    for service in schema_json:
        domain = service['service_name']
        slots_by_domain[domain] = {}
        for slot in service['slots']:
            is_categorical = slot['is_categorical']
            if is_categorical:
                possible_values = slot['possible_values']
            else:
                possible_values = []

            # Don't consider numerical categorical slots as categorical.
            if is_categorical and all([_.isdigit() for _ in possible_values]):
                is_categorical = False
                possible_values = []

            # To be consistent with the slots in the dialogue, rename
            # "book" slots. e.g. "hotel-book people" -> "hotel-people".
            slot_name = slot['name'].replace('book', '')
            slots_by_domain[domain][slot_name] = SlotInfo(
                is_categorical=is_categorical, possible_values=possible_values)
    return SchemaInfo(slots_by_domain)


def get_domain(slot_name: str) -> str:
    """Extracts the domain from a Multiwoz slot name."""
    return slot_name.split('-')[0]


def extract_belief_state(metadata_json: Json, is_trade: bool) -> Dict[str, str]:
    """Extracts belief states from data.

    Args:
      metadata_json: A json dict containing metadata about the dialogue.
      is_trade: Whether the data is trade-preprocessed or not.

    Returns:
      A mapping from slot name to value for the current dialogue.
    """
    state_dict = collections.OrderedDict()

    # Form belief state based on whether data is TRADE preprocessed or not
    if is_trade:
        for state in metadata_json:
            if len(state['slots']) != 1:
                raise ValueError('Length of slots in state must be 1. Actual length: '
                                 f"{len(state['slots'])}. "
                                 f"state['slots']: {state['slots']}")
            # To be consistent with the keys, rename
            # "book" slots. e.g. "hotel-book people" -> "hotel-people".
            slot_name = state['slots'][0][0].replace('book ', '')
            state_dict[slot_name] = state['slots'][0][1]
    else:
        for domain, state in metadata_json.items():
            # Two types of states: book and semi.
            domain_bs_book = state['book']
            domain_bs_semi = state['semi']
            # Note: "booked" is not really a state, just booking confirmation, and
            # val can be "dontcare".
            state_dict.update(
                (f'{domain}-{key}', val)
                for key, val in domain_bs_book.items()
                if val and val not in ('not mentioned', 'none') and key != 'booked')
            state_dict.update((f'{domain}-{key}', val)
                              for key, val in domain_bs_semi.items()
                              if val and val not in ('not mentioned', 'none'))
    return state_dict


def extract_belief_state_for_dstc(metadata_json: Json) -> Dict[str, str]:
    """Extracts belief states from data."""
    state_dict = collections.OrderedDict()
    state_dict.update((key, val) for key, val in metadata_json.items())
    return state_dict


def extract_domains(belief_state: Dict[str, str]) -> Set[str]:
    """Extracts active domains in the dialogue state."""
    return set([get_domain(slot_name) for slot_name in belief_state.keys()])
