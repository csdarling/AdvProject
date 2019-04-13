def append_to_dol(dict_of_lists, key, new_val):
    if key not in dict_of_lists:
        dict_of_lists[key] = []

    dict_of_lists[key].append(new_val)

def convert_list_to_string(lst):
    list_of_strs = [str(val) for val in lst]
    return "".join(list_of_strs)

def add_spaces_to_bitstring(bitstr, idxs, str_len):
    padded_bitstr = ""
    i = 0

    for count in range(str_len):
        if count in idxs:
            padded_bitstr += bitstr[i]
            i += 1
        else:
            padded_bitstr += " "

    return padded_bitstr
