from hypothesis import Verbosity, settings

# Register test profiles
settings.register_profile("dev", max_examples=10)
settings.register_profile("ci", max_examples=100)
settings.register_profile("debug", max_examples=1000, verbosity=Verbosity.verbose)
