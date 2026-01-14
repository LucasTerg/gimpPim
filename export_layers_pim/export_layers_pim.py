#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
from gi.repository import Gimp, GimpUi, GObject, Gio, GLib
import os
import re
import sys

# Nazwy procedur
PROC_LAYERS = "plug-in-export-layers-pim"
PROC_ALL_IMAGES = "plug-in-export-all-images-pim"

def clean_filename(text):
    """Usuwa polskie znaki i znaki specjalne z nazwy pliku."""
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 
        'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 
        'ż': 'z', 'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 
        'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 
        'Ź': 'Z', 'Ż': 'Z'
    }
    
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    text = text.replace(" ", "-")
    text = re.sub(r'-+', '-', text)
    text = text.replace("-.", ".")
    text = re.sub(r'-\.', '.', text) 
    text = re.sub(r'[^a-zA-Z0-9\.-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

class ExportLayersPIM(Gimp.PlugIn):
    """Plug-in do eksportu warstw i obrazów z GIMP-a."""
    __gtype_name__ = "ExportLayersPIM"
    
    def do_query_procedures(self):
        return [PROC_LAYERS, PROC_ALL_IMAGES]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_attribution("PIM", "PIM", "2026")
        
        # Wspólne argumenty dla obu procedur
        procedure.add_string_argument("output-folder", "Folder docelowy", "Wybierz folder zapisu", "", GObject.ParamFlags.READWRITE)
        procedure.add_string_argument("base-name", "Nazwa bazowa", "Nazwa plików (bez polskich znaków)", "produkt", GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("start-number", "Numer początkowy", "Start numeracji", 1, 10000, 1, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("create-subdir", "Utwórz podkatalog", "Utwórz podkatalog o nazwie bazowej", False, GObject.ParamFlags.READWRITE)

        if name == PROC_LAYERS:
            procedure.set_menu_label("Eksportuj warstwy (PIM)...")
            procedure.set_documentation(
                "Eksportuje widoczne warstwy aktywnego obrazu",
                "Zapisuje każdą warstwę jako osobny plik JPG: nazwa-numer.jpg",
                name
            )
            procedure.add_menu_path('<Image>/Filters/gimp-PIM/')
            
        elif name == PROC_ALL_IMAGES:
            procedure.set_menu_label("Eksportuj WSZYSTKIE otwarte (PIM)...")
            procedure.set_documentation(
                "Eksportuje wszystkie otwarte obrazy",
                "Zapisuje każdy otwarty obraz jako plik JPG: nazwa-numer.jpg",
                name
            )
            procedure.add_menu_path('<Image>/Filters/gimp-PIM/')

        return procedure

    def run(self, procedure, *args):
        # Walidacja argumentów
        if len(args) < 4:
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Błędna liczba argumentów", 0))

        run_mode = args[0]
        # Dla PROC_ALL_IMAGES image to po prostu aktywny obraz (jeden z wielu)
        current_image = args[1] 
        
        config = None
        for arg in args:
            if isinstance(arg, Gimp.ProcedureConfig):
                config = arg
                break
        
        if not config:
             return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Nie znaleziono konfiguracji", 0))

        # GUI Dialog
        if run_mode == Gimp.RunMode.INTERACTIVE:
            GimpUi.init(procedure.get_name())
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
            dialog.destroy()
        
        # Pobranie parametrów
        folder_path = config.get_property("output-folder")
        base_name_raw = config.get_property("base-name")
        start_num = config.get_property("start-number")
        create_subdir = config.get_property("create-subdir")
        
        # Logika katalogów
        if not folder_path or folder_path == ".":
            folder_path = os.getcwd()
            
        clean_base = clean_filename(base_name_raw)

        if create_subdir:
            folder_path = os.path.join(folder_path, clean_base)

        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
            except:
                pass

        current_num = start_num
        
        # --- LOGIKA: EKSPORT WARSTW ---
        if procedure.get_name() == PROC_LAYERS:
            all_layers = current_image.get_layers()
            layers_to_export = [layer for layer in all_layers if layer.get_visible()]
            initial_visibility = {layer: layer.get_visible() for layer in all_layers}
            
            current_image.undo_group_start()
            Gimp.context_push()
            
            try:
                for layer in all_layers:
                    layer.set_visible(False)
                    
                for layer in layers_to_export:
                    layer.set_visible(True)
                    
                    filename = f"{clean_base}-{current_num}.jpg"
                    full_path = os.path.join(folder_path, filename)
                    output_file = Gio.File.new_for_path(full_path)
                    
                    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, current_image, output_file)
                    
                    layer.set_visible(False)
                    current_num += 1
                
                for layer, was_visible in initial_visibility.items():
                    layer.set_visible(was_visible)
                    
            except Exception as e:
                sys.stderr.write(f"PIM Export Layers Error: {str(e)}\n")
                return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error.new_literal(Gimp.PlugIn.error_quark(), str(e), 0))
            finally:
                Gimp.context_pop()
                current_image.undo_group_end()

        # --- LOGIKA: EKSPORT WSZYSTKICH OBRAZÓW ---
        elif procedure.get_name() == PROC_ALL_IMAGES:
            # Pobierz wszystkie otwarte obrazy
            images = Gimp.get_images()
            
            # Warto posortować obrazy, np. po ID, żeby kolejność była stała, 
            # ale Gimp.list_images() zwykle zwraca w kolejności otwarcia/utworzenia.
            # Ewentualnie odwrócić listę, jeśli GIMP zwraca stos (LIFO).
            
            for img in images:
                try:
                    filename = f"{clean_base}-{current_num}.jpg"
                    full_path = os.path.join(folder_path, filename)
                    output_file = Gio.File.new_for_path(full_path)
                    
                    # Zapisujemy obraz tak jak jest (spłaszczony widok)
                    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, output_file)
                    
                    current_num += 1
                except Exception as e:
                    sys.stderr.write(f"PIM Export All Error on image {img}: {str(e)}\n")
                    # Kontynuujemy z następnym obrazem zamiast przerywać całość
                    pass

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

Gimp.main(ExportLayersPIM.__gtype_name__, sys.argv)