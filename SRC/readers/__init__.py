def __init__(self, project, input_folder="input"):

    self.project = project

    self.input_folder = Path(input_folder)

    self.file_path = None

    self.doc = None

    self.msp = None