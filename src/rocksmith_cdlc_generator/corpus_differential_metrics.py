from typing import List, Dict

def arrangement_presence_metrics(arrangement_names: List[str]) -> Dict[str, bool]:
    """
    Return a dictionary indicating the presence of bass, lead, and rhythm arrangements,
    and whether they are symmetric.
    
    :param arrangement_names: List of arrangement names
    :return: Dictionary with keys 'bass', 'lead', 'rhythm', and 'symmetric'
    """
    bass_present = any(name.lower() == 'bass' for name in arrangement_names)
    lead_present = any(name.lower() == 'lead' for name in arrangement_names)
    rhythm_present = any(name.lower() == 'rhythm' for name in arrangement_names)
    symmetric = bass_present and lead_present and rhythm_present
    
    return {
        'bass': bass_present,
        'lead': lead_present,
        'rhythm': rhythm_present,
        'symmetric': symmetric
    }
